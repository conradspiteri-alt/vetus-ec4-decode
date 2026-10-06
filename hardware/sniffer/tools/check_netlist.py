#!/usr/bin/env python3
"""
EC4 sniffer carrier - firmware / PCB net-list correlation check.

Reads the pin assignments straight out of the firmware source, maps them to
ESP32-S3-DevKitC-1 header pin numbers using Espressif's official J1 table, then
reads the actual pad nets out of the KiCad board file and compares.

Nothing here is typed by hand twice. Re-run it after ANY change to either file.

    python3 tools/check_netlist.py

Sources for the J1 table:
  https://documentation.espressif.com/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.1.html
"""
import re, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
INO  = os.path.join(REPO, "firmware", "sniffer", "ec4_can_sniffer", "ec4_can_sniffer.ino")
PCB  = os.path.join(REPO, "hardware", "sniffer", "carrier-pcb", "kicad-EC4-Carrier", "EC4-Carrier.kicad_pcb")

# ---------------------------------------------------------------- J1 pin table
# ESP32-S3-DevKitC-1 v1.1, Header J1, pin no. -> signal.
# Taken from the Function column of Espressif's table, NOT the Name column
# (the Name column renders ambiguously in some mirrors of the doc).
J1 = {1:"3V3", 2:"3V3", 3:"RST", 4:"GPIO4", 5:"GPIO5", 6:"GPIO6", 7:"GPIO7",
      8:"GPIO15", 9:"GPIO16", 10:"GPIO17", 11:"GPIO18", 12:"GPIO8", 13:"GPIO3",
      14:"GPIO46", 15:"GPIO9", 16:"GPIO10", 17:"GPIO11", 18:"GPIO12",
      19:"GPIO13", 20:"GPIO14", 21:"5V", 22:"GND"}
SIG2PIN = {}
for n, s in J1.items():
    SIG2PIN.setdefault(s, n)          # 3V3 appears twice; first occurrence wins

# firmware symbol -> the carrier net it must land on
EXPECT_NET = {"PIN_CAN_TX":"CAN_TX", "PIN_CAN_RX":"CAN_RX", "PIN_SD_SCK":"SD_SCK",
              "PIN_SD_MOSI":"SD_MOSI", "PIN_SD_MISO":"SD_MISO", "PIN_SD_CS":"SD_CS"}
# rails that are not in the firmware but must still be right
RAILS = {"3V3":"+3V3", "5V":"+5V", "GND":"GND"}

# ---------------------------------------------------------------- parse firmware
src = open(INO).read()
fw = {}
for m in re.finditer(r'(PIN_[A-Z_]+)\s*=\s*GPIO_NUM_(\d+)', src):
    fw[m.group(1)] = int(m.group(2))
for m in re.finditer(r'(PIN_[A-Z_]+)\s*=\s*(\d+)\s*[,;]', src):
    fw.setdefault(m.group(1), int(m.group(2)))

# also confirm the SPI bus really is begun in the SCK, MISO, MOSI, CS order
spi = re.search(r'sdSPI\.begin\(\s*([A-Z_]+)\s*,\s*([A-Z_]+)\s*,\s*([A-Z_]+)\s*,\s*([A-Z_]+)\s*\)', src)

# ---------------------------------------------------------------- parse the PCB
pcb = open(PCB).read()
i = pcb.find('(footprint "ec4:J1"')
d, j = 0, i
while True:
    if pcb[j] == "(": d += 1
    elif pcb[j] == ")":
        d -= 1
        if d == 0: break
    j += 1
blk = pcb[i:j+1]
def _span(text, start):
    """Return the substring of the balanced s-expression beginning at `start`."""
    d, j = 0, start
    while True:
        if text[j] == "(": d += 1
        elif text[j] == ")":
            d -= 1
            if d == 0: return text[start:j+1]
        j += 1

pcb_net, k = {}, 0
while True:
    k = blk.find('(pad "', k)
    if k < 0: break
    pad = _span(blk, k); k += 1
    num = re.match(r'\(pad "([^"]+)"', pad).group(1)
    if not num.isdigit(): continue
    nm = re.search(r'\(net \d+ "([^"]*)"\)', pad)
    pcb_net[int(num)] = nm.group(1) if nm else ""

# ------------------------------------------------ destination module pin tables
# Read off the boards themselves (silkscreen), not from a datasheet.
# SK Pang Rev B 06/18 host header, pin 1 = the pad nearest the +Vcc end.
J3_LABEL = {1:"+Vcc", 2:"CAN_TX", 3:"CAN_RX", 4:"GND"}
J3_EXPECT = {1:"+3V3", 2:"CAN_TX", 3:"CAN_RX", 4:"GND"}
# SB Components microSD breakout. Silkscreen uses SDIO names; the SPI role is what matters.
J4_LABEL = {1:"3V3", 2:"GND", 3:"CD", 4:"D1", 5:"D0", 6:"CLK", 7:"CMD", 8:"D3", 9:"D2"}
J4_EXPECT = {1:"+3V3", 2:"GND", 3:"", 4:"", 5:"SD_MISO", 6:"SD_SCK", 7:"SD_MOSI", 8:"SD_CS", 9:""}
J4_ROLE  = {5:"MISO", 6:"SCK", 7:"MOSI", 8:"CS"}

def pads_of(ref):
    a = pcb.find(f'(footprint "ec4:{ref}"')
    b = _span(pcb, a)
    out, k = {}, 0
    while True:
        k = b.find('(pad "', k)
        if k < 0: return out
        pad = _span(b, k); k += 1
        num = re.match(r'\(pad "([^"]+)"', pad).group(1)
        if not num.isdigit(): continue
        nm = re.search(r'\(net \d+ "([^"]*)"\)', pad)
        out[int(num)] = nm.group(1) if nm else ""

# ---------------------------------------------------------------- compare
rows, bad = [], 0
def row(sym, sig, pin, want, got):
    global bad
    ok = (want == got)
    if not ok: bad_inc()
    rows.append((sym, sig, pin, want, got, "OK" if ok else "*** MISMATCH ***"))
def bad_inc():
    global bad; bad += 1

for sym, net in EXPECT_NET.items():
    if sym not in fw:
        rows.append((sym, "-", "-", net, "NOT FOUND IN FIRMWARE", "*** MISSING ***")); bad_inc(); continue
    sig = f"GPIO{fw[sym]}"
    pin = SIG2PIN.get(sig)
    if pin is None:
        rows.append((sym, sig, "-", net, "NOT ON HEADER J1", "*** MISMATCH ***")); bad_inc(); continue
    row(sym, sig, pin, net, pcb_net.get(pin, "<no net>"))
for sig, net in RAILS.items():
    pin = SIG2PIN[sig]
    row("(rail)", sig, pin, net, pcb_net.get(pin, "<no net>"))

# destination side
dst = []
for ref, lab, exp, role in (("J3", J3_LABEL, J3_EXPECT, {}), ("J4", J4_LABEL, J4_EXPECT, J4_ROLE)):
    got = pads_of(ref)
    for pin in sorted(lab):
        want = exp[pin]; have = got.get(pin, "<no pad>")
        ok = (want == have) or (want == "" and have == "")
        if not ok: bad_inc()
        r = role.get(pin, "")
        dst.append((f"{ref}.{pin}", lab[pin] + (f" ({r})" if r else ""),
                    want or "(none)", have or "(none)", "OK" if ok else "*** MISMATCH ***"))

w = max(len(r[0]) for r in rows)
print(f"{'firmware':<{w}}  {'signal':<7} {'J1 pin':>6}  {'expected net':<12} {'net on PCB':<12}  result")
print("-" * (w + 60))
for r in rows:
    print(f"{r[0]:<{w}}  {str(r[1]):<7} {str(r[2]):>6}  {r[3]:<12} {str(r[4]):<12}  {r[5]}")

print()
w2 = max(len(r[0]) for r in dst)
print(f"{'module pad':<{w2}}  {'silkscreen':<14} {'expected net':<12} {'net on PCB':<12}  result")
print("-" * (w2 + 58))
for r in dst:
    print(f"{r[0]:<{w2}}  {r[1]:<14} {r[2]:<12} {r[3]:<12}  {r[4]}")

print()
if spi:
    order = spi.groups()
    want = ("PIN_SD_SCK", "PIN_SD_MISO", "PIN_SD_MOSI", "PIN_SD_CS")
    print(f"SPI bus begin order: {', '.join(order)}   ->  "
          + ("OK (SCK, MISO, MOSI, CS)" if order == want else "*** CHECK: expected SCK, MISO, MOSI, CS ***"))
    if order != want: bad_inc()
else:
    print("SPI bus begin call not found  *** CHECK ***"); bad_inc()

# SD silkscreen name trap: carrier pads must carry SPI names, board prints SDIO names
print("SDIO -> SPI mapping on the microSD breakout: CLK=SCK, CMD=MOSI, D0=MISO, D3=CS")

print()
print("NET-LIST CORRELATION: PASS" if bad == 0 else f"NET-LIST CORRELATION: {bad} PROBLEM(S)")
sys.exit(0 if bad == 0 else 1)
