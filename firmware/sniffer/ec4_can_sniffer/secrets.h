// secrets.h: WiFi networks for the EC4 sniffer. EDIT BEFORE FLASHING.
// The firmware refuses to join WiFi while any value still starts with CHANGE_ME,
// and says so on the serial console. SD logging works without WiFi.
//
// If you keep your real credentials in a clone of this repository, run once:
//   git update-index --skip-worktree firmware/sniffer/ec4_can_sniffer/secrets.h
// so your edits are never committed. tools/check_secrets.py checks it before a commit.
#pragma once

struct WifiNet { const char* ssid; const char* pass; };

static const WifiNet WIFI_NETS[] = {
  { "CHANGE_ME_SSID", "CHANGE_ME_PASSWORD" },
};
static const int WIFI_NETS_COUNT = sizeof(WIFI_NETS) / sizeof(WIFI_NETS[0]);

static const char* WIFI_HOSTNAME = "ec4-can";   // http://ec4-can.local/
