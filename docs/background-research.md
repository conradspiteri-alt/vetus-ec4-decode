# EC4 / V-CAN Protocol Research

**Date:** 8 September 2026. Every factual claim carries a source URL. Inference is labelled as such. "Not found" means a genuine gap, not an assumption.

---

## 1. The EC4 is a rebadged Flexball Italiana 4500-series control

The single most useful finding. The Vetus EC4/EC4HSM is manufactured by **Flexball Italiana S.r.l.** (Turin, Italy).

- The Vetus manual 030624.13 r05 (2025) carries a leftover **"Flexball Italiana S.r.l."** running header on p.17. Source: https://vetus.com/wp-content/uploads/030624.13-r05-2025-02-EC4_EC4HSM-EN.pdf
- Flexball's own manual for series 3500/4000/4200/4500 contains, word for word, the same feature set the Vetus manual describes: Fast Start-up Mode, Command/Warm-Sync held "for 1,5 seconds", the "serial number 18500" station limit, the 4-pole DIP table (1 = termination, 2 = trolling, 3-4 = station address), JP14 = actuator CAN address, JP19 = termination, "FI xx" firmware display, parameter "CC" for internal CANBus check, 150 N nominal / 450 N max actuator force. Source: https://abasmarin.no/wp-content/uploads/2020/04/Manual-for-marine-electronic-controls_2019-07-15.pdf ; mirror https://www.mmsab.se/wp-content/uploads/2017/01/Manual-Flexball4000-4500.pdf

Why it matters: Flexball's own documentation (datasheets, selection guides, catalogue) is a second, independent source of detail, and Flexball is contactable directly (+39 011 9038900, info@flexballitaliana.com). Catalogue: https://www.flexballitaliana.com/product-category/marine/electronic-controls.html

**EC4UMM1 decoded.** Vetus lists EC4UMM1 as "Control box, for 1 engine with mechanical throttle and gearshift, 12/24 V". Source: https://webshop.vetus.com/en/products/engines-and-around-the-engine/electronic-engine-remote-controls . Against the Flexball code legend (first letter = throttle type M/V/I/C/W, second = gearbox M/E, digit = engines) EC4-U-M-M-1 = actuator Unit, Mechanical throttle, Mechanical gearbox, 1 engine. The test boat has two, one per engine. Legend source: https://www.flexballitaliana.com/upload/document/513-scheda-4500-selection-guide.pdf

---

## 2. Physical layer (documented)

- Proprietary **CAN bus**, 4-wire M12 data cable, "polarisation code A" for the CAN data cable and "code B" for the engine/throttle cable. Wire colours **white = Signal, yellow = GND** on the data pair. Source: Vetus EC4 manual (above) and Flexball manual (above).
- **120 ohm end-of-line termination**, switch-selectable: JP19 on the actuator (factory ON), DIP switch 1 on the control head. Source: EC4 manual pp.30-38; "JP19 enables (ON) or disables (OFF) the line termination. Factory setting is JP19 = ON."
- Stations are **powered over the CAN cable** from the actuator (a troubleshooting row: "LEDs on command station never illuminate while actuator display is lit" = CAN data cable not delivering power). Source: https://www.manualslib.com/manual/3251089/Vetus-Ec4hsm.html?page=78
- **Addressing:** actuator address by JP14 (OFF = 0, ON = 1); stations by DIP 3-4 (station 1 / FSM / 2 / 3). After serial 18500, unlimited extra stations all use address 3. Source: EC4 manual pp.12-14, 37-38.
- Max ~80 m cockpit to engine room; DTCAN data cables 3-15 m plus 30 m extension. Source: EC4 manual; Flexball 4500 datasheet https://www.flexballitaliana.com/upload/document/537-scheda-4500-electronic-control.pdf

**Not found:** bit rate, CAN identifier format (11-bit vs 29-bit), higher-layer protocol, and the M12 **pin numbers** for CAN_H/CAN_L/V+/V- (only wire colours are given). These must be measured. Do not assume an NMEA 2000 Micro-C drop cable is pin-compatible; forum evidence on the separate V-CAN bus found pin 1 = +12 V, which does **not** match the Micro-C pinout, so verify with a meter.

---

## 3. The "250 kbit/s, 29-bit, J1939" table is a red herring

The Flexball/Vetus manuals do contain a table reading "29 bit in accordance with CAN 2.0B, 250 Kbit/s, 10 ms, Priority/PGN/Address". **It describes the actuator's optional output to an electronic engine ECU, not the station-to-actuator bus.** The surrounding text: "Every CANBus interface card has one output ... This document refers to SAE J1939 ... In the data field you must write the motor speed reference." Source: https://www.bukh-bremen.de/additional_files/german/030624_12_r03_2013_08_ec3_ec4_en_24660.pdf

The test boat's TAMD63P engines are 1998 mechanical with no electronic ECU, so this J1939 output is not in use. The internal lever-to-actuator bus rate remains undocumented.

*Inference:* 250 kbit/s is a reasonable first guess for the station bus too (same hardware family, long cable runs favour lower rates), but it is unverified. Autobaud during sniffing; do not hard-code it.

---

## 4. Vetus V-CAN is a different bus (do not conflate)

- Vetus describes V-CAN as "a proprietary CAN bus system designed exclusively for VETUS products" with CANVERTER gateways to NMEA 2000 and J1939. Source: https://vetus.com/usa/blog/blog-can-bus-systems/
- V-CAN is the bus for **BOW PRO thrusters, E-LINE, RimDrive** and their panels (BPPPA/BPPJA), wireless (CANVWRC) and joystick interfaces. Physical: 12 V bus power, 120 ohm both ends, max 40 m without a CANR repeater, 4-conductor twisted pair. Sources: https://vetus.com/wp-content/uploads/020815.11-r05-2025-05-IM-Proportional-panel-for-bow-and-stern-thruster-BPPPA-BPPJA.pdf ; https://vetus.com/news/press-release-vetus-certified-as-first-thurster-integrator-for-nmea-2000/
- **The EC4 manual never uses the term "V-CAN".** None of Vetus's 13 thruster-integration diagrams show an EC3/EC4 on V-CAN. Source: https://vetus.com/wp-content/uploads/021000.11-r06-2026-01-IM-diagams-thruster-integration.pdf

*Conclusion:* treat EC4 and V-CAN as two unrelated proprietary CAN buses. Research on one does not transfer to the other except as general method. Relevant to the test boat only if a Vetus thruster is fitted; the existing thruster is analogue-solenoid per the hardware brief.

---

## 5. Command arbitration and the safety-critical gap

Documented station-transfer logic (this is the crux for any write path):

- A station takes command only if, after power-up, its lever is in **neutral**, OR its lever is **synchronised** to the lever of the station currently holding command; then Command is held **1.5 s**. Source: Flexball manual, https://www.mmsab.se/wp-content/uploads/2017/01/Manual-Flexball4000-4500.pdf
- Fast Start-up Mode station auto-takes command at power-on **only if in neutral**. Source: EC4 manual pp.11-15.
- **Duplicate station address causes "unpredictable engagement"**: troubleshooting row "Without moving any lever, the actuator generates changes of speed or unpredictable engagement" -> cause "two command stations sharing same CAN address". Source: https://www.manualslib.com/manual/3251089/Vetus-Ec4hsm.html?page=77

*Inferences from this section that bear on bus security are held pending disclosure.*

---

## 6. Documented failure behaviour (thin)

- **Unforeseen shutdown:** mechanical push-pull cables remain connected; operate via mechanical emergency levers (turn knob A fully clockwise, gearbox by levers B, throttle at minimum). Source: EC4 manual s.16.1.1.
- **Actuator self-protection:** "The actuator motor is disabled and the gearbox command is maintained in the last position before the overload occurred." Source: Flexball manual s.16.1.3.
- Actuator display diagnostic parameters: FI (firmware), A0, dI, dA, **CC** (internal CANBus check, values N/F/R/1-9/A), UL/UH, 0L/0H/0F, 1L/1H/1F, PP. Source: EC4 manual.

**Not found, in any manual (2013, 2024, 2025 Vetus, plus two Flexball editions):** what the actuator does when the **commanding station disappears** from the bus, on CAN error, or on power loss **while in gear**. No timeout, no forced-neutral, no buzzer is documented. This is the single most important unknown for the whole project and must be established empirically with an existing head at the dock, engine immobilised.

---

## 7. A non-lever command source exists at the OEM

Flexball sells a **4500 WRC wireless remote** commanding "PORT ENGINE, STARBOARD ENGINE, BOW THRUSTER, [STERN THRUSTER], ANCHOR WINCH" (2.4 GHz). Source: https://www.flexballitaliana.com/upload/document/546-scheda-4500-wrc.pdf

*Significance:* proves the actuator bus accepts commands from something other than a lever head. *Caveat (inference):* the receiver most likely emulates a command station (same address/arbitration rules) rather than using a distinct command message. The datasheet does not state how the receiver attaches to the bus, nor any dead-man/timeout behaviour. Worth a direct question to Flexball, and worth pricing the WRC itself as a possible sanctioned route to remote command (buying the intended product may beat reverse-engineering the bus).

---

## 8. No public reverse-engineering exists

Searches across GitHub, GitLab, Signal K, OpenPlotter, cruisersforum, ybw, boatdesign, Reddit, Hackaday and the canboat project found **nothing** decoding either the EC4/Flexball bus or V-CAN. canboat's NMEA 2000 manufacturer code for Vetus is 1053 ("Vetus Maxwell INC.") with no proprietary PGNs defined; thrusters map to standard PGNs 128006/7/8. Source: https://github.com/canboat/canboat . The only community hardware datum is a barges.org thread on V-CAN cable wiring (not EC4). We are first. Budget accordingly: expect to establish bit rate and framing from scratch.

---

## Most useful facts
1. EC4 = Flexball 4500. Flexball docs and support are a second source.
2. The "250 k / J1939" spec is the engine-ECU output, not the lever bus. Autobaud, do not assume.
3. Physical layer known (4-wire, white=signal/yellow=GND, 120 ohm, M12 code A, bus-powered). Pin numbers and bit rate unknown.
4. Duplicate-address = real unintended gear movement. This is both the attack surface and the sniffing hazard.
5. Loss-of-command behaviour is undocumented. Establish it first, empirically.
6. A sanctioned wireless remote (Flexball WRC) exists; consider buying capability rather than building it.

## Explicit gaps
- Bit rate, CAN ID scheme, payload layout, arbitration message format of the EC4 bus.
- M12 pin map for the EC4 data connector (colours only are documented).
- Actuator behaviour on loss of commanding station / bus error / power loss in gear.
- How the WRC receiver injects commands (station emulation vs dedicated message).
- Whether the EC4 bus is CANopen/J1939-derived or fully bespoke (unconfirmed until sniffed).
