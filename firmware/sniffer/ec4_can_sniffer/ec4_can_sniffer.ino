// ec4_can_sniffer.ino
// EC4 CAN sniffer / SD logger  -  Stage 1, LISTEN-ONLY.
// Target: ESP32-S3-DevKitC-1 (Arduino-ESP32 core v3.x, ESP-IDF v5 TWAI API).
//
// Rev D.3 (Sep 2026): every bus error is timestamped in the CAN task. Errors closer than 50 ms
//   apart are merged into one burst note: "# (t) bus errors N in D ms". Resolution about 5 ms.
// Rev D.2 (Sep 2026): WiFi connect timeout 10 s; late connects and reconnects start the servers.
// Rev D.1 (Sep 2026): rate-change notes carry the CAN task's timestamp.
// Rev D (Sep 2026):
//   - CAN runs in its own task from power-up and timestamps each frame on receipt,
//     so WiFi, HTTP downloads and SD writes can no longer compress timestamps.
//   - Starts listening at 125 kbit/s (the EC4 rate) immediately, so the EC4 boot is
//     captured if the node is powered first. A silent bus just waits. If traffic is
//     present at the wrong rate (bus errors, no frames for 5 s), it steps to the next rate
//     and cycles round; it never gives up. Locks on the first good frame.
//   - A log file is open from boot. WiFi retries every 30 s if it failed at boot.
//   - Phone note page: http://ec4-can.local/mark adds timestamped notes from any helm.
//
// Capture:
//   - TWAI (CAN) LISTEN-ONLY. Never transmits, ACKs, or sends error frames.
//   - Logs every frame to microSD, candump-compatible, file rolling at 8 MB.
//
// Get logs / live view - all three, no cable required except for flashing:
//   - SD card (primary, underway).
//   - WiFi HTTP: browse http://ec4-can.local/ to list and download .log files.
//   - SavvyCAN live: GVRET over USB serial OR over WiFi TCP (port 23). Cable-free.
//
// LISTEN-ONLY throughout. GVRET "send frame" is parsed and discarded; never transmits.

#include "driver/twai.h"
#include <SPI.h>
#include <SD.h>
#include "esp_timer.h"
#include <WiFi.h>
#include <WiFiMulti.h>
#include <WebServer.h>
#include <ESPmDNS.h>
#include "lwip/sockets.h"
#include "secrets.h"

// ---------------- Pin map ----------------
static const gpio_num_t PIN_CAN_TX = GPIO_NUM_5;
static const gpio_num_t PIN_CAN_RX = GPIO_NUM_4;
static const int PIN_SD_SCK = 12, PIN_SD_MOSI = 11, PIN_SD_MISO = 13, PIN_SD_CS = 10;

// ---------------- Options ----------------
static const uint32_t HUNT_WINDOW_MS     = 1000;  // look for errors-without-frames over this window
static const uint32_t HUNT_ERR_THRESHOLD = 8;     // bus errors in a window with 0 frames => suspect wrong rate
static const uint32_t HUNT_ERR_WINDOWS   = 5;     // ...for this many windows in a row before stepping.
                                                  // Rides out a lone EC4 node retrying without ACK at boot.
static const uint32_t WIFI_RETRY_MS      = 30000;
static const uint32_t WIFI_CONNECT_MS    = 10000; // first rev D boot needed ~6.7 s to connect; 4 s was too tight
static const int      RXQ_LEN            = 1024;  // ~29 s of EC4 traffic
static const uint64_t ERR_BURST_GAP_US   = 50000; // bus errors closer than this are one burst
static const uint64_t ERR_BURST_MAX_US   = 1000000; // a continuous storm is split into 1 s notes
static const uint32_t MAX_FILE_BYTES     = 8UL * 1024 * 1024;
static const size_t   WRITE_BUF_BYTES    = 4096;
static const uint32_t FLUSH_INTERVAL_MS  = 2000;
static const char*    IFACE_NAME         = "can0";
static const uint16_t GVRET_TCP_PORT     = 23;   // SavvyCAN "Network (GVRET)" default

// ---------------- State ----------------
SPIClass sdSPI(HSPI);
File     logFile; char currentLogName[24] = {0};
bool     sdOK = false;
uint32_t fileIndex = 0, fileBytes = 0; uint64_t frameCount = 0; uint32_t chosenBitrate = 0;
char     wbuf[WRITE_BUF_BYTES]; size_t wlen = 0; uint32_t lastFlush = 0;

WiFiMulti  wifiMulti;
WebServer  server(80);
WiFiServer gvretServer(GVRET_TCP_PORT);
WiFiClient gvretClient;
bool       wifiUp = false, serversUp = false; uint32_t lastWifiTry = 0;

// CAN task -> loop hand-off. The task owns the TWAI driver; loop owns SD, serial and network.
struct Rx { uint64_t us; twai_message_t m; };
static QueueHandle_t rxq;
// Bus-error bursts, stamped in the CAN task, logged by loop (rev D.3)
struct ErrBurst { uint64_t t0, t1; uint32_t n; uint8_t flags; };   // flags: 1 error passive, 2 bus off
static QueueHandle_t errq;
static volatile uint32_t rxDropped = 0, busErrors = 0;
static volatile bool     rateLocked = false;
static volatile int      rateIdx = 0;
static volatile bool     rateEvent = false;       // loop logs a note when the rate changes or locks
static volatile uint64_t rateEventUs = 0;         // when it happened (CAN task time, not loop time)
static char notes[8][72]; static int noteHead = 0; // last notes, for the /mark page

// GVRET stream routing: one active SavvyCAN link at a time (USB or TCP)
bool     gvretActive = false;
Stream*  gSink = nullptr;

struct RateOpt { uint32_t bps; twai_timing_config_t t; };
static RateOpt RATES[] = {
  { 125000, TWAI_TIMING_CONFIG_125KBITS() }, { 250000, TWAI_TIMING_CONFIG_250KBITS() },
  { 500000, TWAI_TIMING_CONFIG_500KBITS() }, { 1000000, TWAI_TIMING_CONFIG_1MBITS() },
};
static const int NUM_RATES = sizeof(RATES) / sizeof(RATES[0]);

// ---------------- TWAI ----------------
static bool twaiInstallStart(const twai_timing_config_t& t) {
  twai_general_config_t g = TWAI_GENERAL_CONFIG_DEFAULT(PIN_CAN_TX, PIN_CAN_RX, TWAI_MODE_LISTEN_ONLY);
  g.rx_queue_len = 128; g.tx_queue_len = 0;
  twai_filter_config_t f = TWAI_FILTER_CONFIG_ACCEPT_ALL();
  if (twai_driver_install(&g, &t, &f) != ESP_OK) return false;
  if (twai_start() != ESP_OK) { twai_driver_uninstall(); return false; }
  twai_reconfigure_alerts(TWAI_ALERT_RX_DATA | TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF, NULL);
  return true;
}
static void twaiStopUninstall() { twai_stop(); twai_driver_uninstall(); }
// The task owns TWAI: receive, timestamp on receipt, hand to loop. Never transmits.
static void canTask(void*) {
  int idx = 0;
  while (!twaiInstallStart(RATES[idx].t)) vTaskDelay(pdMS_TO_TICKS(500));
  rateIdx = idx; chosenBitrate = RATES[idx].bps; rateEventUs = esp_timer_get_time(); rateEvent = true;
  uint32_t winStart = millis(), winFrames = 0, errBase = 0, errWins = 0;
  twai_status_info_t st; if (twai_get_status_info(&st) == ESP_OK) errBase = st.bus_error_count;
  uint32_t errSeen = errBase; ErrBurst eb = {};
  twai_message_t m;
  for (;;) {
    if (twai_receive(&m, pdMS_TO_TICKS(5)) == ESP_OK) {
      Rx r; r.us = esp_timer_get_time(); r.m = m;
      if (xQueueSend(rxq, &r, 0) != pdTRUE) rxDropped++;
      winFrames++;
      if (!rateLocked) { rateLocked = true; rateEventUs = r.us; rateEvent = true; }
    }
    // rev D.3: timestamp bus errors. The alert is read within one receive timeout (5 ms) of the error.
    uint32_t al = 0;
    if (twai_read_alerts(&al, 0) == ESP_OK && (al & (TWAI_ALERT_BUS_ERROR | TWAI_ALERT_ERR_PASS | TWAI_ALERT_BUS_OFF))) {
      uint64_t now = esp_timer_get_time();
      twai_status_info_t s2;
      if (twai_get_status_info(&s2) == ESP_OK) {
        uint32_t d = s2.bus_error_count - errSeen; errSeen = s2.bus_error_count;
        if (d || (al & TWAI_ALERT_BUS_ERROR)) { if (!eb.n) eb.t0 = now; eb.t1 = now; eb.n += d ? d : 1; }
      }
      if (al & TWAI_ALERT_ERR_PASS) eb.flags |= 1;
      if (al & TWAI_ALERT_BUS_OFF)  eb.flags |= 2;
    }
    if (eb.n) {
      uint64_t now = esp_timer_get_time();
      if (now - eb.t1 > ERR_BURST_GAP_US || now - eb.t0 > ERR_BURST_MAX_US) { xQueueSend(errq, &eb, 0); eb = ErrBurst{}; }
    }
    if (millis() - winStart >= HUNT_WINDOW_MS) {
      uint32_t errs = 0;
      if (twai_get_status_info(&st) == ESP_OK) { errs = st.bus_error_count - errBase; errBase = st.bus_error_count;
                                                 busErrors += errs;
                                                 if (st.state == TWAI_STATE_BUS_OFF) twai_initiate_recovery(); }
      // traffic present but unreadable at this rate: step to the next one (listen-only, harmless to the bus)
      errWins = (!rateLocked && winFrames == 0 && errs >= HUNT_ERR_THRESHOLD) ? errWins + 1 : 0;
      if (errWins >= HUNT_ERR_WINDOWS) {
        errWins = 0;
        twaiStopUninstall();
        idx = (idx + 1) % NUM_RATES;
        while (!twaiInstallStart(RATES[idx].t)) vTaskDelay(pdMS_TO_TICKS(200));
        rateIdx = idx; chosenBitrate = RATES[idx].bps; rateEventUs = esp_timer_get_time(); rateEvent = true;
        if (twai_get_status_info(&st) == ESP_OK) errBase = st.bus_error_count;
        errSeen = errBase; eb = ErrBurst{};                 // new driver instance: counters restart
      }
      winStart = millis(); winFrames = 0;
    }
  }
}

// ---------------- SD ----------------
static void openNextFile() {
  if (logFile) logFile.close();
  while (fileIndex < 100000) {
    snprintf(currentLogName, sizeof(currentLogName), "/ec4can%04lu.log", (unsigned long)fileIndex);
    if (!SD.exists(currentLogName)) break; fileIndex++;
  }
  logFile = SD.open(currentLogName, FILE_WRITE); fileBytes = 0;
  if (logFile) {
    if (!gvretActive) Serial.printf("# log file: %s\n", currentLogName);
    char hdr[112]; int n = snprintf(hdr, sizeof(hdr), "# ec4 sniffer rev D.3 | bitrate %lu%s | file %s\n",
                                   (unsigned long)chosenBitrate, rateLocked ? "" : " (listening, not yet locked)", currentLogName);
    logFile.write((const uint8_t*)hdr, n); fileBytes += n;
  }
  fileIndex++;
}
static void flushBuf() {
  if (wlen && logFile) { logFile.write((const uint8_t*)wbuf, wlen); logFile.flush();
                         fileBytes += wlen; wlen = 0; if (fileBytes >= MAX_FILE_BYTES) openNextFile(); }
  lastFlush = millis();
}
static void bufWrite(const char* s, size_t n) {
  if (!sdOK) return; if (wlen + n > WRITE_BUF_BYTES) flushBuf(); memcpy(wbuf + wlen, s, n); wlen += n;
}
// No default argument: Arduino's auto-prototypes would duplicate it and fail to compile.
static void logCommentAt(const char* text, uint64_t us) {
  char line[160];
  int n = snprintf(line, sizeof(line), "# (%llu.%06llu) %s\n", us/1000000ULL, us%1000000ULL, text);
  bufWrite(line, n); if (gSink != (Stream*)&Serial) Serial.write((const uint8_t*)line, n); flushBuf();
  snprintf(notes[noteHead], sizeof(notes[0]), "%llu.%02llu %s", us/1000000ULL, (us%1000000ULL)/10000ULL, text);
  noteHead = (noteHead + 1) % 8;
}
static void logComment(const char* text) { logCommentAt(text, esp_timer_get_time()); }

// ================= GVRET (SavvyCAN) - USB serial OR WiFi TCP, monitor-only =================
static const uint8_t GVRET_START = 0xF1;
enum { G_IDLE, G_CMD, G_BUILD, G_SETUP, G_SWMODE };
static uint8_t gState = G_IDLE, gBuf[8]; static int gGot = 0, gNeed = 0, gBuildLeft = 0;

static void gvretSendFrame(const twai_message_t& m, uint64_t rxUs) {
  if (!gSink) return;
  uint8_t b[24]; int i = 0; uint32_t us = (uint32_t)rxUs;
  uint32_t id = m.identifier; if (m.extd) id |= (1UL << 31);
  b[i++]=0xF1; b[i++]=0x00; b[i++]=us; b[i++]=us>>8; b[i++]=us>>16; b[i++]=us>>24;
  b[i++]=id; b[i++]=id>>8; b[i++]=id>>16; b[i++]=id>>24;
  uint8_t dlc = m.data_length_code & 0x0F; b[i++]=dlc;
  for (int k=0;k<dlc&&k<8;k++) b[i++]=m.data[k];
  b[i++]=0; gSink->write(b, i);
}
static void gvretExec(uint8_t cmd) {
  if (!gSink) { gState = G_IDLE; return; }
  switch (cmd) {
    case 0x00: gState=G_BUILD; gGot=0; return;
    case 0x01: { uint32_t us=(uint32_t)esp_timer_get_time();
                 uint8_t r[]={0xF1,0x01,(uint8_t)us,(uint8_t)(us>>8),(uint8_t)(us>>16),(uint8_t)(us>>24)}; gSink->write(r,sizeof(r)); break; }
    case 0x06: { uint8_t r[13]; int i=0; r[i++]=0xF1; r[i++]=0x06; r[i++]=(uint8_t)(1|(1<<4));
                 r[i++]=chosenBitrate; r[i++]=chosenBitrate>>8; r[i++]=chosenBitrate>>16; r[i++]=chosenBitrate>>24;
                 r[i++]=0;r[i++]=0;r[i++]=0;r[i++]=0;r[i++]=0; gSink->write(r,i); break; }
    case 0x07: { uint8_t r[]={0xF1,0x07,0x0A,0x03,0,0,0,0}; gSink->write(r,sizeof(r)); break; }
    case 0x08: gState=G_SWMODE; gGot=0; gNeed=1; return;
    case 0x09: { uint8_t r[]={0xF1,0x09,0xDE,0xAD}; gSink->write(r,sizeof(r)); break; }
    case 0x05: gState=G_SETUP; gGot=0; gNeed=10; return;
    case 0x0C: { uint8_t r[]={0xF1,0x0C,1}; gSink->write(r,sizeof(r)); break; }
    case 0x0D: { uint8_t r[12]; r[0]=0xF1; r[1]=0x0D; for(int k=2;k<12;k++) r[k]=0; gSink->write(r,12); break; }
    default: break;
  }
  gState = G_IDLE;
}
static void gvretByte(uint8_t b) {
  switch (gState) {
    case G_IDLE:  if (b==GVRET_START) gState=G_CMD; break;
    case G_CMD:   gvretExec(b); break;
    case G_SWMODE:
    case G_SETUP: if (++gGot >= gNeed) gState=G_IDLE; break;
    case G_BUILD: gBuf[gGot<8?gGot:7]=b; gGot++;
                  if (gGot==5) gBuildLeft=(gBuf[4]&0x0F)+1;
                  else if (gGot>5 && --gBuildLeft<=0) gState=G_IDLE; break;
  }
}

// ---------------- Frame emit ----------------
static void emitFrame(const Rx& r) {
  const twai_message_t& m = r.m;
  uint64_t us = r.us; char line[64]; int n;
  if (m.rtr) n = snprintf(line,sizeof(line),"(%llu.%06llu) %s %0*lX#R\n",
                          us/1000000ULL,us%1000000ULL,IFACE_NAME,m.extd?8:3,(unsigned long)m.identifier);
  else { char d[24]; int p=0; for(int i=0;i<m.data_length_code&&i<8;i++) p+=snprintf(d+p,sizeof(d)-p,"%02X",m.data[i]); d[p]=0;
         n = snprintf(line,sizeof(line),"(%llu.%06llu) %s %0*lX#%s\n",
                      us/1000000ULL,us%1000000ULL,IFACE_NAME,m.extd?8:3,(unsigned long)m.identifier,d); }
  bufWrite(line, n);                                    // SD: always candump
  if (gvretActive) gvretSendFrame(m, us);               // GVRET (USB or TCP)
  else Serial.write((const uint8_t*)line, n);           // else USB candump ASCII
}

// ---------------- WiFi + HTTP log server ----------------
static void handleIndex() {
  flushBuf();
  String h = "<!doctype html><meta name=viewport content='width=device-width,initial-scale=1'>";
  h += "<style>body{font-family:system-ui;margin:1rem}a{color:#06c}</style><h2>EC4 sniffer CAN logs</h2>";
  h += "<p>bitrate " + String(chosenBitrate) + " · frames " + String((unsigned long)frameCount)
     + " · <a href='/roll'>start new file</a> · <a href='/mark'>add notes</a></p><ul>";
  File dir = SD.open("/");
  for (File f = dir.openNextFile(); f; f = dir.openNextFile()) {
    String nm = f.name(); if (nm.startsWith("/")) nm = nm.substring(1);
    if (nm.endsWith(".log")) h += "<li><a href='/dl?f=" + nm + "'>" + nm + "</a> (" + String((unsigned long)f.size()) + " B)</li>";
    f.close();
  }
  dir.close(); h += "</ul><p>SavvyCAN live: Network (GVRET), IP above, port " + String(GVRET_TCP_PORT) + "</p>";
  server.send(200, "text/html; charset=utf-8", h);
}
static void handleDownload() {
  flushBuf(); String f = server.arg("f"); String path = "/" + f;
  bool active = (String(currentLogName) == path);
  if (active && logFile) logFile.close();
  File dl = SD.open(path, FILE_READ);
  if (!dl) server.send(404, "text/plain", "not found");
  else { server.sendHeader("Content-Disposition", "attachment; filename=" + f);
         server.streamFile(dl, "application/octet-stream"); dl.close(); }
  if (active) logFile = SD.open(currentLogName, FILE_WRITE);
}
static void handleRoll() { if (sdOK) { flushBuf(); openNextFile(); } server.sendHeader("Location","/"); server.send(303); }
static void handleStatus() {
  server.send(200, "text/plain; charset=utf-8", "bitrate " + String(chosenBitrate) + (rateLocked ? " locked" : " listening") +
    "\nframes " + String((unsigned long)frameCount) + "\ndropped " + String((unsigned long)rxDropped) +
    "\nbus_errors " + String((unsigned long)busErrors) +
    "\nfile " + String(currentLogName) + "\nsd " + String(sdOK?"ok":"FAIL") + "\ngvret " + String(gvretActive?"active":"idle") + "\n");
}

// Phone note page: one tap per test step, from any helm on the boat WiFi.
static const char MARK_PAGE[] PROGMEM = R"HTML(<!doctype html><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>EC4 sniffer notes</title>
<style>body{font:16px system-ui;margin:12px;background:#10161a;color:#e3e9eb}
h1{font-size:20px;margin:4px 0 10px}form{display:flex;gap:6px}input{flex:1;font:16px system-ui;padding:10px;border-radius:8px;border:1px solid #3a474e;background:#1a2227;color:#e3e9eb}
button{font:600 15px system-ui;padding:12px 10px;border-radius:8px;border:1px solid #3a474e;background:#23303a;color:#e3e9eb}
.g{display:grid;grid-template-columns:1fr 1fr;gap:6px;margin:10px 0}.g button{text-align:left}
h2{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#8c9aa0;margin:14px 0 4px}
#ok{min-height:1.4em;color:#4ccb85}#last{font:13px ui-monospace,monospace;color:#8c9aa0;white-space:pre-line}</style>
<h1>EC4 sniffer capture notes</h1>
<form id=f><input id=t placeholder="Type a note" autocomplete=off><button>Add</button></form>
<div id=ok></div>
<h2>Main helm</h2><div class=g>
<button>main: command</button><button>main: warm-up throttle</button><button>main: warm off</button><button>main: sync on</button>
<button>main: sync right lever</button><button>main: sync left lever</button><button>main: sync off</button><button>main: warm on</button></div>
<h2>Flybridge</h2><div class=g>
<button>fly: refused command</button><button>fly: command</button><button>fly: port lever</button><button>fly: stbd lever</button>
<button>fly: warm off</button><button>fly: sync on</button><button>fly: sync right lever</button><button>fly: sync left lever</button>
<button>fly: sync off</button><button>fly: warm on</button></div>
<h2>Other</h2><div class=g>
<button>boot: EC4 power on</button><button>main: synced, engine LEDs blinking</button><button>main: took command under way</button><button>trim</button>
<button>actuator display</button><button>step done</button></div>
<h2>Last notes</h2><div id=last></div>
<script>
const ok=document.getElementById('ok'),last=document.getElementById('last');
async function send(x){if(!x)return;ok.textContent='sending...';
 try{const r=await fetch('/note?text='+encodeURIComponent(x));ok.textContent=r.ok?('logged: '+x):'failed';refresh();}catch(e){ok.textContent='no connection to the sniffer';}}
async function refresh(){try{last.textContent=await (await fetch('/notes')).text();}catch(e){}}
document.getElementById('f').onsubmit=e=>{e.preventDefault();const t=document.getElementById('t');send(t.value.trim());t.value='';};
document.querySelectorAll('.g button').forEach(b=>b.onclick=()=>send(b.textContent));
refresh();
</script>)HTML";
static void handleMark() { server.send_P(200, "text/html; charset=utf-8", MARK_PAGE); }
static void handleNote() {
  String t = server.arg("text"); t.trim();
  if (!t.length()) { server.send(400, "text/plain", "empty note"); return; }
  if (t.length() > 60) t = t.substring(0, 60);
  for (size_t i = 0; i < t.length(); i++) if (t[i] == '\n' || t[i] == '\r') t[i] = ' ';
  logComment(t.c_str());
  server.send(200, "text/plain", "ok");
}
static void handleNotes() {
  String out;
  for (int k = 7; k >= 0; k--) { const char* n = notes[(noteHead + k) % 8]; if (n[0]) { out += n; out += "\n"; } }
  server.send(200, "text/plain; charset=utf-8", out.length() ? out : String("no notes yet"));
}
static void wifiInit() {
  WiFi.mode(WIFI_STA); WiFi.setHostname(WIFI_HOSTNAME);
  for (int i = 0; i < WIFI_NETS_COUNT; i++) {
    if (strncmp(WIFI_NETS[i].ssid, "CHANGE_ME", 9) == 0 || strncmp(WIFI_NETS[i].pass, "CHANGE_ME", 9) == 0) {
      Serial.println("# WiFi disabled: edit secrets.h (placeholder CHANGE_ME values). SD logging continues.");
      return;
    }
  }
  for (int i = 0; i < WIFI_NETS_COUNT; i++) wifiMulti.addAP(WIFI_NETS[i].ssid, WIFI_NETS[i].pass);
}
static bool wifiTold = false;   // one "no network" line per outage; never text into a USB GVRET stream
static void wifiOnConnected() {
  bool first = !serversUp;
  wifiUp = true; wifiTold = false;
  if (gSink != (Stream*)&Serial) Serial.printf("# WiFi %s  IP %s  http://%s.local/  notes: /mark  (SavvyCAN GVRET-TCP port %u)\n",
                WiFi.SSID().c_str(), WiFi.localIP().toString().c_str(), WIFI_HOSTNAME, GVRET_TCP_PORT);
  if (first) {
    MDNS.begin(WIFI_HOSTNAME);
    server.on("/", handleIndex); server.on("/dl", handleDownload);
    server.on("/roll", handleRoll); server.on("/status", handleStatus);
    server.on("/mark", handleMark); server.on("/note", handleNote); server.on("/notes", handleNotes);
    server.begin(); MDNS.addService("http", "tcp", 80);
    gvretServer.begin(); gvretServer.setNoDelay(true);
    serversUp = true;
  }
}
static void wifiTry(uint32_t timeoutMs) {
  lastWifiTry = millis();
  if (wifiMulti.run(timeoutMs) == WL_CONNECTED) { wifiOnConnected(); return; }
  if (!wifiTold && gSink != (Stream*)&Serial) { Serial.println("# WiFi: no known network yet, retrying every 30 s"); wifiTold = true; }
  wifiUp = false;
}
// Rev D.2: a connect that completes after wifiMulti.run() timed out used to leave the
// servers unstarted and 'wifi down' forever. Poll the real state instead.
static void wifiService() {
  bool linked = (WiFi.status() == WL_CONNECTED);
  if (linked && !wifiUp) { wifiOnConnected(); return; }               // late connect or reconnect
  if (!linked && wifiUp) { wifiUp = false; lastWifiTry = millis();    // lost it: let auto-reconnect try first
                           if (gSink != (Stream*)&Serial) Serial.println("# WiFi lost, retrying"); return; }
  if (!linked && millis() - lastWifiTry > WIFI_RETRY_MS) wifiTry(WIFI_CONNECT_MS);
}

// ---------------- USB serial commands ----------------
static char cmdBuf[128]; static size_t cmdLen = 0;
static void handleSerial() {
  while (Serial.available()) {
    uint8_t c = Serial.read();
    // A TCP SavvyCAN may own the GVRET stream, but the serial console stays usable.
    bool tcpOwns = (gvretActive && gSink == (Stream*)&gvretClient);
    if (!tcpOwns && gvretActive && gSink == (Stream*)&Serial) { gvretByte(c); continue; }
    if (!tcpOwns && c == GVRET_START) { gvretActive = true; gSink = (Stream*)&Serial; gState = G_CMD; cmdLen = 0; continue; }
    if (c == '\r') continue;
    if (c == '\n') { cmdBuf[cmdLen] = 0;
      if (cmdLen) switch (cmdBuf[0]) {
        case 'n': logComment(cmdBuf + 1); break;
        case 's': if (gSink != (Stream*)&Serial)
                    Serial.printf("# bitrate %lu %s | frames %llu | dropped %lu | bus errors %lu | wifi %s | gvret %s | sd %s\n",
                      (unsigned long)chosenBitrate, rateLocked ? "locked" : "listening", (unsigned long long)frameCount,
                      (unsigned long)rxDropped, (unsigned long)busErrors,
                      wifiUp?WiFi.localIP().toString().c_str():"down",
                      gvretActive?(gSink==(Stream*)&gvretClient?"tcp":"usb"):"idle", sdOK?"ok":"FAIL"); break;
        case 'd': if (gvretClient) { Serial.println("# GVRET client dropped by console");
                    gvretClient.stop(); if (gSink==(Stream*)&gvretClient) { gvretActive=false; gSink=nullptr; } }
                  else Serial.println("# no GVRET client attached"); break;
        case 'r': if (sdOK) { flushBuf(); openNextFile(); } break;
        default: Serial.println("# cmds: n<text> note | s status | r new file | d drop gvret"); break;
      }
      cmdLen = 0;
    } else if (cmdLen < sizeof(cmdBuf) - 1) cmdBuf[cmdLen++] = c;
  }
}

// ---------------- GVRET-over-TCP servicing ----------------
static void handleGvretTcp() {
  if (!wifiUp) return;
  // accept a new client (one at a time)
  if (gvretServer.hasClient()) {
    if (gvretClient && gvretClient.connected()) gvretServer.available().stop(); // refuse a 2nd
    else {
      gvretClient = gvretServer.available(); gvretActive = true;
      gSink = (Stream*)&gvretClient; gState = G_IDLE;
      gvretClient.setNoDelay(true);
      // TCP keepalive: a crashed SavvyCAN leaves a half-open socket that never FINs.
      int fd = gvretClient.fd();
      if (fd >= 0) { int on=1, idle=10, intvl=3, cnt=3;
        setsockopt(fd, SOL_SOCKET,  SO_KEEPALIVE,  &on,    sizeof(on));
        setsockopt(fd, IPPROTO_TCP, TCP_KEEPIDLE,  &idle,  sizeof(idle));
        setsockopt(fd, IPPROTO_TCP, TCP_KEEPINTVL, &intvl, sizeof(intvl));
        setsockopt(fd, IPPROTO_TCP, TCP_KEEPCNT,   &cnt,   sizeof(cnt)); }
      Serial.printf("# GVRET client attached from %s (console still live, 'd' drops it)\n",
                    gvretClient.remoteIP().toString().c_str());
    }
  }
  if (gvretActive && gSink == (Stream*)&gvretClient) {
    if (!gvretClient.connected()) { gvretClient.stop(); gvretActive = false; gSink = nullptr;
                                    Serial.println("# GVRET client detached"); return; }
    while (gvretClient.available()) gvretByte(gvretClient.read());
  }
}

// ---------------- Setup ----------------
void setup() {
  Serial.begin(115200); uint32_t t0 = millis(); while (!Serial && millis()-t0 < 2000) {}
  Serial.println("\n# EC4 sniffer rev D.3 (listen-only)");
  rxq = xQueueCreate(RXQ_LEN, sizeof(Rx));
  errq = xQueueCreate(32, sizeof(ErrBurst));
  // CAN first, so nothing on the bus is missed while SD and WiFi come up
  xTaskCreatePinnedToCore(canTask, "can", 4096, nullptr, 5, nullptr, 1);
  sdSPI.begin(PIN_SD_SCK, PIN_SD_MISO, PIN_SD_MOSI, PIN_SD_CS);
  if (SD.begin(PIN_SD_CS, sdSPI)) { sdOK = true; Serial.println("# SD mounted"); openNextFile(); }
  else Serial.println("# SD mount FAILED - logging to serial only");
  logComment("logging started (rev D.3)");
  wifiInit();
  wifiTry(WIFI_CONNECT_MS);
}

// ---------------- Loop ----------------
void loop() {
  handleSerial();
  if (wifiUp) { server.handleClient(); handleGvretTcp(); }
  Rx r; int burst = 0;
  while (burst < 200 && xQueueReceive(rxq, &r, 0) == pdTRUE) { frameCount++; emitFrame(r); burst++; }
  if (rateEvent) {
    rateEvent = false; char msg[64];
    snprintf(msg, sizeof(msg), rateLocked ? "bitrate locked %lu" : "listening at %lu", (unsigned long)chosenBitrate);
    logCommentAt(msg, rateEventUs);                      // stamped when it happened, not when logged
  }
  ErrBurst eb;
  while (xQueueReceive(errq, &eb, 0) == pdTRUE) {         // rev D.3: one note per burst, stamped at its first error
    char msg[80];
    snprintf(msg, sizeof(msg), "bus errors %lu in %.1f ms%s%s", (unsigned long)eb.n, (double)(eb.t1 - eb.t0) / 1000.0,
             (eb.flags & 1) ? ", error passive" : "", (eb.flags & 2) ? ", bus off" : "");
    logCommentAt(msg, eb.t0);
  }
  if (wlen && (millis() - lastFlush >= FLUSH_INTERVAL_MS)) flushBuf();
  wifiService();
  static uint32_t lastDropReport = 0, lastDrop = 0;
  if (rxDropped != lastDrop && millis() - lastDropReport > 5000) {
    char msg[48]; snprintf(msg, sizeof(msg), "rx queue overflow, %lu frames dropped", (unsigned long)rxDropped);
    logComment(msg); lastDrop = rxDropped; lastDropReport = millis();
  }
  if (!burst) delay(2);
}
