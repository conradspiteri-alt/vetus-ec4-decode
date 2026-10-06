# EC4 sniffer firmware

`ec4_can_sniffer/ec4_can_sniffer.ino` with `secrets.h` beside it: listen-only CAN sniffer and SD logger for the ESP32-S3-DevKitC-1. Hardware: `../../hardware/sniffer/`.

## What it does
- TWAI (CAN) **LISTEN-ONLY**: never transmits, ACKs, or sends error frames. Cannot disturb the bus.
- **Rev D receiver:** runs in its own task from power-up, listening at 125k (the EC4 rate). A silent bus just waits; it locks on the first frame (`bitrate locked 125000` note). If traffic is present but unreadable for 5 s it steps 250k / 500k / 1M and cycles round. It never gives up.
- Each frame is timestamped on receipt, so WiFi, downloads and SD writes cannot bunch timestamps. A 1024-frame buffer covers ~29 s of stall; overflows are logged as notes.
- A log file is open from boot, so an EC4 power-up is captured if the node is on first. WiFi retries every 30 s.
- Logs every frame to microSD, candump-compatible, rolling at 8 MB (`/ec4canNNNN.log`).
- **Three ways to get logs off it:** pull the SD card; download over **WiFi**; live **GVRET** to SavvyCAN over USB.
- **Rev D.3 bus-error notes:** every bus error is timestamped in the CAN task (resolution about 5 ms). Errors closer than 50 ms apart become one note, `# (t) bus errors N in D ms`, with `, error passive` or `, bus off` appended if the controller reached that state. A continuous storm is split into 1 s notes. The playback page draws them as solid purple marks on the Bus errors row; missed frames (inferred from gaps in periodic IDs) are drawn as outlined purple marks for any firmware revision.
- Serial commands: `n<text>` note/marker, `s` status, `r` new file, `d` drop the GVRET client.
- The serial console stays live while SavvyCAN is connected over TCP. `d` force-drops a stuck client.
- Timestamps are µs since boot (no RTC). Use `n` markers, or the phone note page, to bracket each test step.

## Phone note page (rev D)
On the boat WiFi, open **http://ec4-can.local/mark** (or `http://<IP>/mark`) on a phone. One tap logs a timestamped note; buttons match the capture-2 steps, plus a free-text box (60 chars max). Works from either helm; no laptop at the node. `/notes` shows the last 8. Android phones may not resolve `.local`; use the IP from the hotspot or router client list, or the serial boot line.

## secrets.h (WiFi credentials)
`ec4_can_sniffer/secrets.h` ships with placeholder values (`CHANGE_ME_SSID`, `CHANGE_ME_PASSWORD`). Edit it with your own networks before flashing; add more `{ "ssid", "password" }` lines to join whichever is in range. While any value still starts with `CHANGE_ME`, the firmware does not start WiFi and says so on the serial console; SD logging still works.

To keep your real credentials out of git, run once in your clone:

    git update-index --skip-worktree firmware/sniffer/ec4_can_sniffer/secrets.h

and run `python3 tools/check_secrets.py` before committing.

## Arduino IDE setup
1. Arduino IDE 2.x, install **esp32 by Espressif** (v3.x) in Boards Manager.
2. Board: **ESP32S3 Dev Module**.
3. Tools:
   - **USB CDC On Boot: DISABLED** (critical). The node lives in a sealed box and is flashed through the **UART** connector, so `Serial` must map to UART0 via the on-board bridge. The bridge asserts DTR/RTS, so the bootloader is entered automatically and you never need the BOOT button.
   - Flash Size: match your board (8 MB for N8, 16 MB for N16R8).
   - PSRAM: **OPI PSRAM** if N16R8, else Disabled.
   - Upload Speed: 921600. Partition Scheme: default.
4. Open `ec4_can_sniffer/ec4_can_sniffer.ino`; `secrets.h` is already beside it. Edit it first.
5. microSD formatted **FAT32**.

## Wiring (matches the diagrams)
- CAN: GPIO5→SK Pang TXD, GPIO4←SK Pang RXD, 3V3→VCC1, GND→GND1.
- SD (SPI): SCK=12, MOSI=11, MISO=13, CS=10, 3V3→VCC, GND→GND. Flaky init → 10k MISO/CS pull-ups.

## Getting logs over WiFi
On boot the node joins a network from `secrets.h` and prints its IP. Browse **http://ec4-can.local/** (or the IP) to see the log list, download any `.log`, or click **start new file** to close the active one first (cleanest download of what you just captured). `/status` gives a plain-text status.

Caveat: downloading a large file blocks the loop, so CAN draining pauses during the transfer. Pull logs when capture isn't critical (tied up, or between runs), not mid-manoeuvre.

## Live SavvyCAN - over WiFi (no cable) OR over USB
Two ways, pick either:
- **WiFi (cable-free):** in SavvyCAN, Connection → add **Network Connection (GVRET)**, enter the board's IP (shown on the web page and serial), port **23**. Connect. This is the cable-free live view you want at the dock.
- **USB serial:** add a **Serial (GVRET)** connection on the board's COM port (the UART bridge). The firmware auto-switches ASCII→GVRET on the first 0xF1 byte. Lid-off only - the enclosure has no data port.

Only one SavvyCAN link at a time (a second is refused). SD logging continues throughout. **Monitor-only** - SavvyCAN "send frame" is discarded; the node never transmits. GVRET handshake is best-effort and **needs bench validation** against your SavvyCAN version; if it won't connect, note the version and I'll fix it. SD + HTTP don't depend on GVRET.

So: **WiFi carries both** - HTTP file download AND live GVRET. The USB cable is only needed for flashing and as a GVRET fallback.

## Sealed enclosure
The box has no data opening. Power arrives through an M12 cable gland: a cut USB-A lead from the power bank, terminated on J2 (lower hole VIN, upper hole GND). The only other penetration is the panel-mount M12 for the CAN tail. Flashing and card swaps are lid-off jobs. The lid is 5 mm solid PLA with no window, so the module's RGB LED is **not** visible when closed - status comes from WiFi or serial only.

## Do NOT keep a laptop connected underway
The boat slams in a seaway. Log to SD on the power bank, laptop ashore. WiFi/GVRET are dockside tools.

## Planned for the next firmware update: gear status on NMEA 2000 (decided 2 Oct 2026)

View only, for the chart plotter. The sniffer stays listen-only on the EC4 bus; the gear status goes out over WiFi to the Actisense W2K-2, which puts it on the NMEA 2000 {National Marine Electronics Association 2000} network. No wire joins the two buses.

**Message:** PGN {Parameter Group Number} 127493, Transmission Parameters, Dynamic. Priority 2, 8 bytes, sent every 100 ms (the standard interval), one message per engine.

| Byte | Field | Value sent |
|---|---|---|
| 0 | Instance | 0 port (from 0x384), 1 starboard (from 0x485). Must match the engine instances already used on the network (Actisense EMU-1) |
| 1, bits 0-1 | Transmission gear | 0 forward (actuator 44), 1 neutral (C0), 2 reverse (48), 3 unknown |
| 1, bits 2-7 | Reserved | all 1 |
| 2-3 | Oil pressure | FFFF, not available |
| 4-5 | Oil temperature | FFFF, not available |
| 6 | Discrete status 1 | 00 |
| 7 | Reserved | FF |

**Rules:**
- Source is the actuator byte (what the gearbox is doing), never the lever byte (what a helm asks for).
- 4C (shifting): keep sending the last stable gear for up to 1.5 s, then send 3 (unknown). A shift that never completes shows as unknown, not as the old gear.
- 40 (booting) or any undocumented code: send 3.
- No actuator frame for 1 s (EC4 off, or the sniffer lost the bus): stop sending for that engine. The plotter then drops the value instead of showing a stale gear.
- Throttle is not published: no standard PGN field fits, and the station frame carries lever demand, not throttle position.
- Runs in the WiFi or loop task. It must never block or delay the CAN receive task or SD logging.
- One TCP {Transmission Control Protocol} client to the W2K-2 (address and port in `config.json`, data server set to receive). Reconnect every 30 s when down. Anything received on that socket is discarded.
- Published build: included, off by default.

**Check before enabling:**
1. Nothing else on the network sends 127493 for instances 0 and 1 (the EMU-1 can send transmission data). Two sources for one instance make the plotter flicker between them. The W2K-2 EBL logs answer this once downloaded.
2. The plotter displays gear from 127493.
3. The exact W2K-2 input format (N2K ASCII or Actisense) and which source address it uses on the network, from the W2K-2 manual and a bench test.
4. Security: a W2K-2 data server set to receive lets any device on the boat WiFi send messages onto NMEA 2000, autopilot commands included. Before enabling it, change the W2K-2 default login, confirm the boat WiFi uses WPA2 with a strong key, and use a PGN filter on that server, allowing only 127493, if the W2K-2 offers one.

**Later:** when the automatic-manoeuvre system is built, gear and propulsion state travel on its own planned links, not on NMEA 2000. The plotter display continues from one source only; this sniffer output is switched off when the replacement source starts.

---

## Connect → flash → test (do this on the bench first)

### 1. Flash
1. Plug the DevKitC **UART** port into the laptop (the one labelled UART, not USB). It enumerates through the CH343/CP210x bridge whatever state the firmware is in.
2. Select the board and COM port in Arduino IDE.
3. Upload. The bridge auto-resets into the bootloader, so no button dance. If you ever flash through the **USB** connector instead, set USB CDC On Boot back to Enabled first, and expect to hold **BOOT** and tap **RESET** by hand.
4. Open Serial Monitor at **115200**.

### 2. First boot with no bus (sanity)
Expect: `# SD mounted`, `# log file: /ec4canNNNN.log`, `logging started (rev D.3)`, `listening at 125000`, then the WiFi line. `s` shows `listening`. This confirms SD, serial and WiFi without any CAN source.

### 3. Bench CAN source (prove capture)
Give it real traffic one of these ways:
- A second ESP32/Arduino + transceiver transmitting at 250k, or
- A USB-CAN adapter (with SavvyCAN generating frames), or
- Any live CAN bus you can safely tap (e.g. a car OBD-II at 500k).

Wire SK Pang CANH/CANL to that bus (short stub, don't add a terminator if the bus already has two). Expect `bitrate locked 125000` (or the source's rate after a few seconds of hunting), frames to stream in the monitor, and `/ec4can0000.log` to appear on the card. Move the source's data and watch bytes change.

### 4. Test WiFi pull
Within range of a network from `secrets.h`, reboot. The monitor prints the IP and `http://ec4-can.local/`. Browse it, download the `.log`, open it in SavvyCAN (File → Load Log File). Confirm it parses.

### 5. Test GVRET live
- **WiFi:** SavvyCAN → Network (GVRET), the board's IP, port 23. Connect. Confirm live frames. No cable.
- **USB:** close the Serial Monitor, SavvyCAN → Serial (GVRET) on the COM port. Confirm live frames.
If either won't connect, record the SavvyCAN version for a handshake fix. Only one link at a time.

### 6. microSD endurance / format check
Confirm the card is FAT32 and files roll at 8 MB (drop MAX_FILE_BYTES temporarily to test rolling quickly if wanted).

---

## Then on the boat (later)
1. Power the EC4 bus (ignition on, engines off). Meter the M12: 120Ω... expect ~60Ω across CAN_H/CAN_L (two terminators in parallel); identify H/L pins.
2. Compare the ordered Vetus CANT to an installed EC4 T-junction. If it matches, insert it mid-chain; plug the box's M12 onto the spare female. Change NO DIP switch, NO JP19.
3. Power the ESP32 first, then the EC4, to capture the boot. Watch for `bitrate locked 125000`.
4. Run a controls calibration pass (levers ahead/neutral/astern, throttle sweep, station transfer) sending `n` markers as you go.
5. Pull the logs over the boat WiFi (or the card). Decode in SavvyCAN, looking for the authority-transfer frame first, then lever/gear bytes.
