# Listen-only EC4 sniffer: hardware

A galvanically isolated, listen-only CAN logger that plugs into the Vetus EC4 bus through the OEM T-piece, logs every frame to microSD in candump format, and serves the logs over WiFi. It produced every capture in this repository.

> Listen-only by design: the CAN controller runs in TWAI listen-only mode and never transmits, acknowledges or sends error frames. Nothing on the bus is reconfigured: no DIP switch, no JP19, no address, no terminator.

## Contents

| Path | What |
|---|---|
| `BOM.csv`, table below | Every part needed to build one unit, including the T-piece (Y-cable), power and enclosure hardware |
| `tap.md` | How the T-piece goes into the bus, and the isolation rule |
| `carrier-design-brief.md` | Carrier PCB rev B design record: board data, net list, mechanical, verification, enclosure rev B, sealed-build notes |
| `carrier-pcb/kicad-EC4-Carrier/` | KiCad project, KiCad 7 file format (20221018). The title block still reads rev A; the layout is rev B (88 x 74 mm). Opening in a newer KiCad converts it on save |
| `carrier-pcb/EC4-Carrier-revB-gerbers.zip` | Fabrication files as ordered, 2-layer, 1.6 mm |
| `carrier-pcb/*.svg`, `EC4-Carrier-Drawing.pdf` | Concept, layout, schematic and dimensioned drawing |
| `enclosure/EC4-Enclosure.scad` | OpenSCAD source, enclosure rev B |
| `enclosure/*.stl` | Base and lid, print-ready |
| `enclosure/EC4-Enclosure-Drawing.pdf`, `-Views.png` | Dimensioned drawing and renders |
| `diagrams/` | Wiring (pin-accurate), harness pinout, circuit, block diagram, housing layout |
| `tools/check_netlist.py` | Checks the PCB nets against the GPIO numbers in the firmware. `python3 tools/check_netlist.py` |

Firmware: `../../firmware/sniffer/`.

## Architecture

ESP32-S3-DevKitC-1 (TWAI listen-only, SD logging, WiFi HTTP and GVRET for SavvyCAN) on a carrier PCB with an SK Pang ISO1050 isolated CAN board and a microSD breakout. Power: a USB-A power bank into a 5 V screw terminal through a PTC fuse, series Schottky and TVS. The bus side is isolated by the ISO1050 and its own isolated DC-DC; the power bank floats, so the barrier is real.

**Isolation rule.** If the unit is ever fed from boat 12 V, use an isolated 12 V to 5 V converter upstream of J2. A non-isolated buck ties the logic side to boat negative, which is also the EC4 bus ground, and the barrier stops meaning anything.

## Bill of materials

One unit. Line cost is what you pay, so parts sold in packs carry the pack price. Prices GBP ex VAT; "est." lines are indicative, others are supplier prices of September 2026.

| Group | Ref | Qty | Part | Manufacturer / part no. | Supplier | Line £ | Basis | Notes |
|---|---|---|---|---|---|---|---|---|
| Bus tap (Y-cable) | T1 | 1 | CAN-bus T-piece M12 A-coded 5-pin (2 female + 1 male) | Vetus CANT | vetus-shop.com | 50.83 | Supplier list 8 Sep 2026 | The Y-cable. Inline in an interior DTCAN link; the box plugs onto the spare female. Passes the bus straight through |
| Bus tap (Y-cable) | X1 | 1 | M12 A-coded 5-pin male panel connector IP67 with leads or solder cups | Any (match the panel hole in the enclosure) |  | 8.00 | est. | Plugs directly onto the CANT spare female. Only CAN_H (black) and CAN_L (blue) and 0 V (brown) are wired. +24 V (white) and pin 5 (grey) capped |
| Bus tap (Y-cable) | W1 | 0.2 m | Twisted pair 0.25 to 0.5 mm2 tinned | Any |  | 0.50 | est. | X1 to the SK Pang 3-way CAN terminal. Ferrules on the screw-terminal ends |
| Bus tap (Y-cable) | X2 | 0 | M12 A-coded 5-pin male-female extension 0.3 to 1 m | Any |  | 0.00 | est. | Optional. Only if the box cannot sit on the T. Keep the stub under 1 m |
| Electronics | U1 | 1 | ESP32-S3-DevKitC-1 v1.1 (N8 or N16R8) with headers fitted | Espressif ESP32-S3-DevKitC-1 | Any | 14.00 | est. | Soldered pins-down into the carrier. Antenna end over the board notch |
| Electronics | U2 | 1 | Isolated CAN breakout 3.3 V (TI ISO1050 with isolated DC-DC) | SK Pang Electronics isolated CAN-Bus breakout rev B 06/18 | skpang.co.uk | 31.50 | Supplier list 8 Sep 2026 | No terminator fitted (54.6 kohm measured across CAN_H/CAN_L). 3.3 V logic jumper confirmed |
| Electronics | U3 | 1 | microSD breakout SPI 9-pin with pull-ups | SB Components microSD card breakout | Any | 5.00 | est. | Silkscreen uses SDIO names; carrier silk shows the SPI names |
| Electronics | SD1 | 1 | microSD card 8 to 32 GB FAT32 (high-endurance preferred) | Any |  | 6.00 | est. | Files roll at 8 MB |
| Electronics | PCB1 | 1 | Carrier PCB rev B 88 x 74 mm L-shape 2-layer 1.6 mm 1 oz HASL | Gerbers: carrier-pcb/EC4-Carrier-revB-gerbers.zip | JLCPCB or PCBWay | 7.73 | PCBWay 16 Sep 2026: USD 10.24 for 5 at 1.3252 | Minimum order 5 |
| Electronics | F1 | 1 | PTC fuse 1.1 A hold 2.2 A trip 30 V radial 5.08 mm | Bourns MF-R110 | RS 647-8522 | 2.59 | RS 16 Sep 2026 |  |
| Electronics | D2 | 1 | Schottky 40 V 1 A DO-41 | onsemi 1N5819G | RS 774-3347 | 1.40 | RS 16 Sep 2026 | Series diode; stops J2 back-feeding a USB host |
| Electronics | D1 | 1 | TVS 600 W 6.8 V bidirectional DO-15 | ST P6KE6V8CA | RS 486-1130 | 4.57 | RS 16 Sep 2026 | Bidirectional on purpose (no polarity error). Do not use SA5.0A (conducts at power-bank voltage) |
| Electronics | C1 | 1 | Electrolytic 100 uF 16 V 6.3 x 11 mm 2.5 mm pitch | Panasonic ECA1CM101 | RS 228-6650 | 0.90 | RS 16 Sep 2026 |  |
| Electronics | C2 | 1 | Ceramic 100 nF 50 V X7R 5.08 mm | Vishay K104K15X7RF5TH5 | RS 852-3277 | 1.00 | RS 16 Sep 2026 |  |
| Electronics | J2 | 1 | 2-way PCB screw terminal 3.50 mm pitch (3.81 also fits) | Phoenix Contact MKDS 1/2-3.5 | RS 467-0259 | 0.60 | est. | 5.08 mm pitch does NOT fit the pads |
| Electronics | J3 | 1 | Male pin header 1 x 4 2.54 mm | Any |  | 0.20 | est. | SK Pang to carrier |
| Electronics | J4 | 1 | Male pin header 1 x 9 2.54 mm | Any |  | 0.20 | est. | microSD to carrier |
| Power | PB1 | 1 | USB power bank USB-A output 5 V 10000 mAh or more | Any |  | 15.00 | est. | Floating supply keeps the isolation barrier meaningful. About 40 h at about 150 mA (est.) |
| Power | W2 | 1 | USB-A lead cut to bare wire 1 m | Any |  | 2.00 | est. | Meter which conductor is +5 V before terminating on J2 |
| Power | G1 | 1 | Cable gland M12 3 to 6.5 mm IP68 with locknut | RS PRO | RS 669-4654 | 5.04 | RS 16 Sep 2026 | Power lead entry. 12.5 mm panel hole |
| Power | FER | 6 | Bootlace ferrules 0.5 mm2 | Any |  | 0.20 | est. | J2 and the SK Pang CAN terminal |
| Enclosure | ENC1 | 1 | Enclosure base and lid 3D printed (enclosure/EC4-Enclosure-base.stl and -lid.stl) | Print |  | 2.50 | est. (about 100 g filament) | ASA or PETG for an engine space; the test unit was PLA. 4+ perimeters if sealed |
| Enclosure | INS | 6 | M3 brass heat-set inserts (4.0 mm hole) | Any |  | 0.60 | est. | 4 for the corner bosses; 6 if adding mid-span lid screws |
| Enclosure | SCR1 | 6 | M3 x 12 lid screws A4 stainless | Any |  | 0.50 | est. | 4 or 6 as above |
| Enclosure | SCR2 | 2 | M3 screws with nuts or inserts (SK Pang holes) | Any |  | 0.20 | est. | Printed spacers at the measured seated header height |
| Enclosure | SCR3 | 2 | M2 screws with nuts (microSD far holes only) | Any |  | 0.20 | est. | Printed spacers at the measured seated header height |
| Enclosure | SO1 | 1 | 6 mm bonded standoff under the SK Pang DB9 end | Print or nylon spacer |  | 0.10 | est. | Mandatory. Bond with epoxy or CA. No screw |
| Enclosure | FOAM | 1 | EVA foam sheet 1.5 mm | Any |  | 0.50 | est. | Lid hold-down pads and rib: the clamp that stops the board buzzing |
| Enclosure (sealed build) | SEAL | 0.4 m | Silicone cord 2 to 3 mm | Any |  | 4.00 | est. | In a 2.2 x 2.5 mm lid groove |
| Enclosure (sealed build) | VENT | 1 | Pressure-equalising vent membrane IP67 (ePTFE) | Any (Gore-type) |  | 5.00 | est. | Stops the box pumping damp air through the seal |
| Installation | MNT | 1 | Bracket or ties to structure | Any |  | 1.00 | est. | The box must not hang on the M12 joint |
| Tools and consumables | - | - | Solder; heat-shrink; multimeter; Arduino IDE 2.x with esp32 by Espressif 3.x | Owner |  | 0.00 |  | Meter CAN_H to CAN_L (about 60 to 67 ohm EC4 off) and continuity connector-to-transceiver before trusting a capture |

| Group | GBP ex VAT |
|---|---|
| Bus tap (T-piece, panel connector, wire) | 59.33 |
| Electronics | 75.69 |
| Power | 22.24 |
| Enclosure | 4.60 |
| Sealed-build extras | 9.00 |
| Installation | 1.00 |
| **Total** | **about 172** |

## Build notes that matter

- **J2 pitch.** The pads take a 3.50 or 3.81 mm terminal. The 5.08 mm terminal found in most parts drawers does not fit.
- **Spacer height** for the SK Pang and microSD equals the seated header height. Measure it; do not assume 2.5 mm.
- **The 6 mm bonded standoff under the SK Pang DB9 end is mandatory.** Both of its holes are on the header edge, so the board is a 50 mm cantilever with the DB9 mass on the end; engine vibration excites it.
- **Firmware setting:** USB CDC On Boot DISABLED; flash through the UART connector.
- **Before any capture:** meter about 60 to 67 ohm across CAN_H and CAN_L with the EC4 off, and check continuity from each M12 pin to the transceiver. An open CAN_L still receives, badly: see `docs/protocol.md` section 9.

## Enclosure: source against the as-built unit

`EC4-Enclosure.scad` and the STLs are **rev B**: a UART port opening (12 x 9 mm), a 16 x 11 mm opening for the M12 tail, a 13 x 10 mm power slot and a 0.6 mm LED window in a 2.5 mm lid. The unit on the boat was built sealed: panel-mount M12, a 12.5 mm hole for the M12 power gland, no port opening and a 5 mm solid lid with no window (firmware README). Those changes are not in the source. Treat the STLs as the rev B baseline and cut the sealed-build holes to suit the panel connector you fit.
