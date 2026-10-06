# EC4 sniffer - carrier PCB design brief (v0.8, rev B)

**Date:** 16 September 2026. Consolidated. Supersedes v0.3 to v0.7.
Companion files: `carrier-pcb/Carrier-PCB-Layout.svg`, `carrier-pcb/kicad-EC4-Carrier/`, `enclosure/`.
Wiring source of truth: `diagrams/Sniffer-Wiring-PinAccurate.svg`. Firmware: `../../firmware/sniffer/ec4_can_sniffer/ec4_can_sniffer.ino`.

One PCB carrying the **ESP32-S3-DevKitC-1**, the **SK Pang isolated CAN board**, the
**SB Components microSD breakout**, and a **screw-terminal 5 V input**. The M12 connector is
NOT on the PCB: its CAN_H / CAN_L / 0V land directly on the SK Pang's own screw terminal.

---

## 1. What changed in rev B, and why

| Change | Reason |
|---|---|
| Board **81 -> 88 mm wide** | Through-hole passives need the room. Also puts the SK Pang's DB9 and CAN terminal fully over the carrier instead of overhanging it |
| **All passives through-hole** | Hand assembly |
| Enclosure lid-screw bosses moved **outside the cavity** | In rev A they sat directly on the carrier footprint. A real error, caught by inspection of the render |
| **DB9 fully enclosed**, no wall opening | It is unused. A hole in the side of a box on a boat is a water path for no benefit |
| **One** DevKitC port opening, not two | See section 7 - it is a firmware decision, not just a hole |
| Component **body** clearance check added to the process | Copper DRC passed a board on which two parts physically collided. See section 6 |

---

## 2. Board data, all confirmed by measurement

### ESP32-S3-DevKitC-1
- **70.0 x 26.0 mm**, headers already fitted, pins down, soldered straight into the carrier.
- 2 x 22 pins, **2.54 mm** pitch, rows **22.86 mm** apart.
- **Pin 22 is 8.00 mm from the USB-end edge**, so pin 1 is at 61.34 mm and **8.66 mm of board projects beyond pin 1 - that is the antenna.**
- Two USB connectors at the pin 22 / 23 end: **USB** (native) at the pin-1-column side, **UART** (bridge) at the other.

### SK Pang Rev B 06/18 isolated CAN-Bus (ISO1050)
- **47.0 x 50.0 mm x 1.6 mm.** Datum = corner nearest +Vcc; X along the 47 mm header edge, Y into the 50 mm depth.
- Header **1 x 4, 2.54 mm**, pin 1 at **(8.0, 2.8)**, order **+Vcc, CAN_TX, CAN_RX, GND** (MCU-referenced).
- Mounting holes **3.0 mm** at **(3, 3)** and **(44, 3)**. Both on the header edge - see section 5.
- DB9 and the 3-way CAN terminal are at the opposite end, overhanging the board edge by **5 mm**.
- Logic side confirmed **3.3 V**.
- **54.6 kohm** across CAN_H / CAN_L on the bench: **no terminator fitted**. In parallel with the EC4's 60 ohm that is 59.94 ohm, a 0.1 % perturbation. Safe for mid-bus insertion.

### SB Components microSD breakout
- **25.0 x 35.0 mm x 1.6 mm** (37 mm with a card in).
- Header **1 x 9, 2.54 mm**, pin 1 (3V3) at **(2.34, 5.0)**.
- Silkscreen uses **SDIO names, not SPI names.** The carrier silkscreen prints the SPI equivalents.
- Four holes **2.0 mm** at (2,2), (23,2), (2,33), (23,33). **Only the far pair is used.**
- R1-R8 on the breakout are the line pull-ups, so the carrier carries none.

---

## 3. Carrier - 88.0 x 74.0 mm, L-shaped

Bounding box 88 x 74, less a **29.0 x 10.5 mm** notch at the top left. Origin bottom-left, viewed component side.

| Item | Position |
|---|---|
| DevKitC board | X 2-28, Y 0-70, USB flush with the Y=0 edge |
| DevKitC pad rows | X 3.57 and 26.43; pins Y 8.00 to 61.34, step 2.54 |
| Antenna notch | X 0-29, Y 63.5-74 removed from the outline |
| SK Pang board | X 31-81, Y 0-47; DB9 + CAN terminal to X 86, now over the carrier |
| SK Pang header pads | X 33.8; Y 8.00 (+Vcc), 10.54 (CAN_TX), 13.08 (CAN_RX), 15.62 (GND) |
| SK Pang M3 holes | (34, 3) and (34, 44), 3.4 mm clearance |
| SK Pang bonded standoff | 6 mm pad at (74, 23.5), no hole |
| SD board | X 31-66, Y 49-74; header faces -X, card ejects +X |
| SD header pads | X 36.0; Y 51.34 to 71.66, step 2.54 (3V3 first) |
| SD M2 holes | (64, 51) and (64, 72), 2.4 mm clearance |
| J2 terminal | pads (73, 51.400) and (73, 55.055), oval 2.0 x 1.4 mm |
| F1 PTC | pads (76.08, 63.5) = VIN, (71.00, 63.5) = VF, 5.08 mm pitch |
| D2 Schottky | pads (70.50, 70.5) = VF, (78.12, 70.5) = +5V, 7.62 mm pitch |
| D1 TVS | pads (82.50, 57.50) = GND, (82.50, 67.66) = +5V, 10.16 mm pitch |
| C1 bulk | pads (84.00, 68.75) = +5V, (84.00, 71.25) = GND, 2.5 mm pitch |
| C2 ceramic | pads (85.50, 56.58) = +5V, (85.50, 51.50) = GND, 5.08 mm pitch |

### The notch
Pin 1's pad reaches Y=62.24, so the outline stops at **Y=63.5**, leaving 1.26 mm of annular material. The DevKitC's last 6.5 mm then hangs over free air. WiFi is the only cable-free route to the logs; a ground plane 1 mm under the antenna is a self-inflicted range loss.

---

## 4. Net list - verified automatically, see section 6

| Net | DevKitC pin | To |
|---|---|---|
| +3V3 | P1 | SK Pang +Vcc, SD 3V3 |
| GND | P22 | SK Pang GND, SD GND, J2 0V, D1, C1, C2 |
| +5V | P21 | D2 cathode, D1, C1, C2 |
| CAN_TX | GPIO5 (P5) | SK Pang CAN_TX |
| CAN_RX | GPIO4 (P4) | SK Pang CAN_RX |
| SD_SCK | GPIO12 (P18) | SD **CLK** |
| SD_MOSI | GPIO11 (P17) | SD **CMD** |
| SD_MISO | GPIO13 (P19) | SD **D0** |
| SD_CS | GPIO10 (P16) | SD **D3** |

SD **D1**, **D2**, **CD** unused. Power chain: J2 -> F1 -> D2 -> +5V rail, D1 across it to GND, C1 and C2 on it.
D2 in series stops the terminal back-feeding a connected USB host, so bench-over-USB and terminal-5V can coexist.

Bus side, NOT on the PCB: SK Pang screw terminal -> M12 CAN_H, CAN_L, 0V. The +12 V lead and the unused grey pin-5 lead are capped.

**Carry-forward:** when this is hard-wired to boat 12 V later, put an **isolated** 12 V -> 5 V brick upstream of J2. A non-isolated buck would tie the logic side to boat DC negative, which is also the EC4 bus ground, and the SK Pang barrier would stop meaning anything.

---

## 5. Mechanical - what the mounting holes can and cannot do

**DevKitC:** both 2x22 rows soldered, every pin. Supported on both long edges. No cantilever.

**SK Pang:** both of its holes sit on the header edge. They do **not** oppose the cantilever, they duplicate the support the header already gives. The board projects 50 mm from that line with the DB9 shell and two steel jackposts (~10 g) on the end. At 2,400 rpm the TAMD63P firing frequency is 120 Hz, with slam content at 5-20 Hz beneath it. A cantilevered board with a mass on the end has a first bending mode easy to land in that range. **The 6 mm bonded standoff under the DB9 end is mandatory.** No screw, no hole - it bears on the underside and takes the bending load without stressing anything.

**microSD:** the two holes beside the header are 2.9 mm from the header centreline; an M2 standoff at 4 mm across leaves 0.35 mm to the pin 1 pad. **Far pair only.**

**Spacer height must equal the seated header height.** Measure it once the headers are in; do not assume 2.5 mm. A spacer taller or shorter fights the soldered joint and the screw levers the pins.

---

## 6. Verification - three checks, and what they do not prove

1. **Copper clearance**, written against the source geometry: every track against every pad, hole, via, other track and board edge at a **0.20 mm** rule. JLCPCB's floor is 0.127 mm. **PASS.**
2. **Component body clearance** (new in rev B): the plan-view outline of every real part against every other part, the module boards, the SD card sweep and the board edge, at **0.50 mm**. **PASS**, minimum gap 0.75 mm.
3. **KiCad DRC**: **0 errors, 0 unconnected pads, 0 footprint errors.** Remaining warnings are silkscreen cosmetics the fab clips.

**Why check 2 exists.** The rev A board passed copper DRC with two parts physically colliding: F1's body overlapped the J2 terminal by 0.78 mm and D1's overlapped the C1 can by 0.95 mm. DRC checks copper, not part bodies. It would have been found on the bench with a scrapped board.

4. **Firmware-to-PCB net-list correlation** (new): `tools/check_netlist.py`. **PASS, end to end.**

### How check 4 works, and why it replaces eyeballing
The earlier version of this document asked you to compare the net list against the firmware by hand. That is exactly the kind of check a human does badly and a script does perfectly, so it is now a script. It:

1. Parses the GPIO numbers **out of `../../firmware/sniffer/ec4_can_sniffer/ec4_can_sniffer.ino`** itself. Nothing retyped.
2. Maps each GPIO to a DevKitC header pin using **Espressif's official Header J1 table** for the ESP32-S3-DevKitC-1 v1.1, transcribed from the *Function* column (the Name column renders ambiguously in some mirrors).
3. Parses the **actual pad nets out of `EC4-Carrier.kicad_pcb`**, with proper s-expression matching rather than a regex that trips over nested parentheses.
4. Walks the far end too: SK Pang J3 pads 1-4 against their silkscreen, and microSD J4 pads 1-9 against the **SDIO-to-SPI role** each one has to carry.
5. Separately confirms `sdSPI.begin()` is called in SCK, MISO, MOSI, CS order, which is the other easy way to get SPI wrong.

Run it after any change to either file:

    python3 tools/check_netlist.py      # exit 0 = pass, 1 = problem

The only assumption left is the J1 table itself, and that now comes from Espressif rather than from me. It independently confirms the mapping used throughout: P1=3V3, P4=GPIO4, P5=GPIO5, P16=GPIO10, P17=GPIO11, P18=GPIO12, P19=GPIO13, P21=5V, P22=GND.

**What is still not proven.** The script checks that the board matches the firmware's intent. It cannot tell you the intent was right in the first place - for example that CAN_TX really should drive the SK Pang pad labelled CAN_TX rather than the other one. That judgement stands on the MCU-referenced labelling confirmed in section 2, and on the bench test.

---

## 7. The one port opening - this is a firmware decision

The DevKitC has two USB connectors and only one gets a hole.

| | **UART** (bridge) - recommended | **USB** (native) |
|---|---|---|
| Flashing | Auto-resets into the bootloader. No buttons, ever | Needs BOOT + RESET by hand if the firmware crashes USB |
| Enumeration | Always, regardless of firmware state | Only if the firmware brings up CDC |
| Firmware setting | **USB CDC On Boot: DISABLED**, Serial maps to UART0 | USB CDC On Boot: Enabled, as the firmware README says today |
| Sealed box | Never needs opening to recover | Lid off and finger on BOOT to recover |

**DECIDED: UART.** `PORT = "UART"` in the .scad, and `../../firmware/sniffer/README.md` has been updated - "USB CDC On Boot" is now **DISABLED**, and the flashing instructions point at the UART connector. SD logging, WiFi HTTP and GVRET-over-TCP are unaffected.

The enclosure is now going fully sealed with no data opening, so neither port is externally accessible and flashing is a lid-off job either way. UART still earns its keep there: a firmware that crashes USB CDC stops enumerating on the native port entirely, and the bridge does not care what the firmware is doing.

---

## 8. Routing, for the record

Two layers, **Manhattan discipline**: every horizontal on B.Cu, every vertical on F.Cu, a via at each corner. That is why nothing crosses on the same layer. 57 tracks, 33 vias, 0.25 mm trace, 0.8 / 0.4 mm vias. GND poured on both layers, excluded above y=61.

The SD and CAN signals cross the DevKitC's right pin row **between pads**, at the 1.27 mm midpoints. Tightest copper clearance on the board is **0.295 mm**, there.

Signals dodge the SK Pang's own M3 holes. The hole at (34, 44) sets the right-hand limit for the four SD risers at 31.9 mm. The hole at (34, 3) is why the 5 V and 3V3 lanes sit at y=6.5 and y=5.6 rather than lower.

---

## 9. Enclosure rev B - 104.4 x 90.4 x 33 mm

- Walls, floor and lid 2.5 mm. Cavity 88.4 x 74.4 x 28 mm. Shell 93.4 x 79.4; the four **external corner bosses** take it to 104.4 x 90.4.
- **The bosses are outside the cavity by design.** Anything inside it fouls the carrier, because the carrier fills the cavity. They double as tie-down points if you drill them through.
- Carrier drops onto a 2 mm perimeter ledge 5 mm above the floor. **No screws through the carrier, no mounting holes in it.**
- The lid carries a hold-down rib along the carrier's free left edge plus four pads, all stopping **1.5 mm** above the board. **Put 1.5 mm EVA foam on each.** That is the clamp, and it is what stops the board buzzing in the ledge.
- Four M3 heat-set inserts (4.0 mm hole) in the bosses; lid screws counterbored.
- **Height is set by the DB9 at 25.7 mm above the floor**, leaving 4.8 mm headroom. Removing the DB9 would buy only 2.5 mm, because the isolated DC-DC is next at 23.2 mm.
- Openings: **front** = one DevKitC port, 12 x 9 mm. **Right** = M12 tail to the CAN terminal, 16 x 11 mm, and a separate 13 x 10 mm slot for the 5 V leads. Nothing else. The DB9 is sealed inside.
- **Lid window** 18 x 12 mm thinned to 0.6 mm over the DevKitC, for the on-module RGB status LED. Print the lid in a light colour and it glows through.
- No SD slot in the wall. Card access is lid-off.

---

## 10. Fabrication and shopping list

**PCB:** JLCPCB, 2-layer, 1.6 mm, 1 oz, HASL, green. Minimum order 5, about GBP 2 plus shipping.

**Through-hole passives, RS part numbers:**

| Ref | Part | RS stock no. | Pack | £ ex VAT |
|---|---|---|---|---|
| F1 | Bourns **MF-R110** PTC, 1.1 A hold / 2.2 A trip, 30 V, radial 5.08 mm | 647-8522 | 10 | 2.59 |
| D2 | onsemi **1N5819G** Schottky, 40 V 1 A, DO-41 | 774-3347 | 10 | 1.40 |
| D1 | ST **P6KE6V8CA** TVS, 600 W, DO-15 | 486-1130 | 10 | 4.57 |
| C1 | Panasonic **ECA1CM101**, 100 uF 16 V, 6.3 x 11 mm, 2.5 mm pitch | 228-6650 | 5 | 0.90 |
| C2 | Vishay **K104K15X7RF5TH5**, 100 nF 50 V X7R | 852-3277 | 5 off | 1.00 |
| - | RS PRO **M12 cable gland**, 3-6.5 mm, IP68, locknut included | 669-4654 | 5 | 5.04 |

**J2** is a 2-way PCB screw terminal. Before fitting, confirm the pitch is
**3.50 or 3.81 mm**. The J2 pads are ovals centred on 3.655 mm and accept either, but they will NOT
accept the 5.08 mm 2-way terminal that is the most common thing in a parts drawer. Body envelope
available is about 13 mm along the pitch axis and as deep as needed toward the board edge.

**Substitutions and why:**
- **D1 is bidirectional, not unidirectional.** RS stocks no 6.8 V unidirectional TVS in DO-15. Same
  5.8 V stand-off and 6.45-7.14 V breakdown; on a DC rail already fronted by a series Schottky the
  symmetry costs nothing, and it removes a polarity error from the build. The obvious alternative,
  Vishay SA5.0A, was rejected: its 5.0 V stand-off sits below a power bank's 5.1-5.25 V output, so it
  would conduct continuously.
- **F1 body is 8.9 x 3 mm**, not the 8 mm circle used in the fit model. Every clearance around it
  improves; nearest neighbour is now 1.09 mm to the SD card sweep.

**Power entry: gland, not a USB-C connector.** The supply is a USB-A power bank, and USB-A is always
5 V live, so the USB-C CC pull-down problem does not arise. A USB-A lead is cut, the bare end fed
through the M12 gland from outside, and terminated on J2. **Panel hole 12.5 mm**, replacing the
13 x 10 mm slot in the rev B enclosure model. Thread the compression nut onto the cable BEFORE
terminating, and meter the cable to confirm which conductor is +5 V - cheap leads do not always
honour red and black.

**Headers - the bit people forget:** 1 x 4 and 1 x 9 male pin headers, 2.54 mm, for the SK Pang and the microSD. The DevKitC needs none.

**Mechanical:** 2 x M3 and 2 x M2 screws with nuts or heat inserts; printed spacers at the measured seated header height; the bonded standoff plus epoxy or CA; 4 x M3 heat-set inserts and 4 x M3 x 12 lid screws; 1.5 mm EVA foam sheet; a USB-A to bare-wire lead for the power bank; bootlace ferrules.

---

## 11a. Sealed enclosure - the owner's revision

The enclosure is being reworked to a **fully sealed** design: no holes, power in through a **panel-mount USB-C**, CAN in through the **panel-mount M12** already purchased. Four points that decide whether it works.

**1. USB-C needs CC pull-downs, or it delivers nothing.** A USB-C receptacle acting as a power sink must present **5.1 kohm to GND on both CC1 and CC2**. Without them a USB-C source sees no sink attached and never turns the 5 V on. This is the single most common way this exact plan fails, and it fails silently. Either buy a panel-mount USB-C **with the CC resistors fitted** (check the listing explicitly, many do not have them), or fit two 5.1 kohm resistors at the connector. It cannot be fixed on the carrier, because the carrier's input is a plain 5 V / 0 V terminal. A USB-A to USB-C lead sidesteps it, since the A end is always live, but that is a constraint you will forget in two years.

**2. A sealed box on a boat needs a vent, or it fills with water.** The ESP32 warms the box, pressure rises, air escapes past the seal. It cools, pressure drops, and it draws damp air back in. Over a season the moisture accumulates and condenses on the coldest surface, which is the PCB. The fix is a **pressure-equalising vent membrane** (ePTFE, Gore-type), M12 threaded or adhesive, IP67. It passes air and blocks liquid water. Counter-intuitively, the vent is what makes the sealing work rather than what defeats it.

**3. FDM prints are porous.** A sealed box printed at normal settings leaks through the walls, not the joint. Print with 4+ perimeters and high flow, or coat the inside with epoxy. Do not assume the seal is the only path.

**4. Four corner screws on a 104 x 90 lid is marginal for even seal compression**, and printed parts warp. Add two mid-span screws on the long sides, and prefer a **2-3 mm silicone cord in a 2.2 x 2.5 mm groove** over a hard O-ring; the cord is far more forgiving of a bowed lid.

### Additional BOM for the sealed build
- Panel-mount USB-C receptacle, IP67, **with 5.1 kohm CC pull-downs fitted**
- Panel-mount M12 A-coded connector (already purchased)
- Pressure-equalising vent membrane, IP67
- Silicone cord, 2-3 mm, for the lid groove
- 2 extra M3 inserts and screws if going to six lid fixings

## 11. Before you order
1. ~~Re-check the net list against the firmware~~ - **done, automated.** `python3 tools/check_netlist.py`, PASS.
2. ~~Confirm the SK Pang 3.3 V jumper~~ - **confirmed by the owner, 16 September 2026.** The carrier feeds +3V3 straight to +Vcc with no level shifting, and that is correct.
3. ~~Decide UART or USB~~ - **UART, decided. Firmware README updated.**
4. Open the .kicad_pcb and eyeball the 3D view against your physical boards.
5. Order 5 boards. Print one base and one lid. Fit the bonded standoff before anything goes on a boat.

All decisions closed. Rev B was fabricated and built; the full parts list is in `BOM.md`.
