# Vetus EC4 station bus: observed protocol

Version 0.2, 6 October 2026. Dr.FireFly. Licence CC BY 4.0.

An independent, listen-only decode of the CAN bus between the control heads and the actuator boxes of a Vetus EC4 electronic engine control (made by Flexball Italiana, 4500 series). Every value comes from captures on one installation unless it is tagged otherwise. Nothing here was checked by Vetus or Flexball.

Tags: **[M]** measured in a capture, **[I]** inferred from the captures, **[Manual]** from the Vetus EC4 manual 030624.13 (2024), linked not reproduced: https://vetus.com/wp-content/uploads/030624.13-r03-2024-10-EC4_EC4HSM-EN.pdf

Machine-readable versions: `dbc/ec4.dbc` (SavvyCAN, cantools) and `data/reference/*.csv`.

> Do not transmit on an engine-control bus. A wrong frame can engage a gearbox or open a throttle. This document describes what the bus carries, not how to drive it.

## 1. Installation and captures

| Item | Value |
|---|---|
| Boat | Fairline Phantom 42, twin Volvo Penta TAMD63P (mechanical engines, no engine ECU) |
| Control | Vetus EC4, owner-installed, every parameter at factory default |
| Stations | 2 twin-lever heads (EC4H2): node 1 main helm, node 2 flybridge |
| Actuators | 2 boxes (EC4UMM1): node 4 port, node 5 starboard. They are the physical bus ends and carry the 120 ohm terminators (JP19 on) |
| Tap | Vetus CANT T-piece inserted in an interior link, listen-only sniffer on its spare port. Nothing on the bus reconfigured. See `hardware/sniffer/` |

| Capture | File | Date | Frames | Duration | Content |
|---|---|---|---|---|---|
| 1 | `captures/capture1.log` | 23 Sep 2026 | 5,522 | 158 s | Main helm only, unlabelled. Timestamps compressed for the first 0.47 s (firmware rev C backlog) |
| 2 | not published | 27 Sep 2026 | 45,520 | 1,533 s | Both helms, all modes, two power-ons, 37 labelled notes. 73 frames missed by the sniffer (section 9) |
| 3 | `captures/capture3.log` | 2 Oct 2026 | 19,786 | 578 s | Frame-loss check after the sniffer repair, labelled fast reversals. Zero frames missed |
| - | `captures/capture1b.log` | 24 or 25 Sep 2026 | 3,868 | 113 s | Unlabelled, not used for the decode |

## 2. Physical layer

- 125 kbit/s, 11-bit identifiers, CANopen-like numbering (TPDO and heartbeat IDs follow CANopen; there is no NMT master) [M].
- Drop connector M12 A-coded, standard colours: **black CAN_H, blue CAN_L**, brown 0 V, white +24 V, grey unused [M]. 67 ohm across CAN_H and CAN_L with the EC4 off: two 120 ohm terminators in parallel plus wiring [M].
- Bus load about 2.4 % [M].
- The bus is a daisy chain. Exactly two terminators, at the physical ends [Manual]. A listen-only tap adds none.

## 3. Nodes and identifiers

Only eight IDs appeared in 71,094 frames. Nothing on NMT 0x000, SYNC 0x080, EMCY or SDO [M].

| ID | Node | Content | Bytes | Period [M] |
|---|---|---|---|---|
| 0x181 | 1, main helm | Station frame: flags and levers | 7 | 150 ms |
| 0x282 | 2, flybridge | Station frame, same layout | 7 | 150 ms |
| 0x384 | 4, port actuator | Status byte | 1 | 153.6 ms |
| 0x485 | 5, starboard actuator | Status byte | 1 | 153.6 ms |
| 0x701 | 1 | Heartbeat, 05 operational | 1 | 500 ms |
| 0x702 | 2 | Heartbeat | 1 | 500 ms |
| 0x704 | 4 | Heartbeat, 00 once at boot then 05 | 1 | 512 ms |
| 0x705 | 5 | Heartbeat, 00 once at boot then 05 | 1 | 512 ms |

- The stations run on a 150 ms grid and the actuators on 153.6 ms, so actuator frames drift through the station frames. There is no fixed phase between a lever change and the next actuator frame [M].
- Station addresses are set by DIP switches 3 and 4 on each head: station 1 OFF/OFF, Fast Start-up Mode ON/OFF, station 2 OFF/ON, station 3 ON/ON [Manual]. Station address appears to equal the CAN node number for nodes 1 and 2 [I].

## 4. Station frame, 0x181 and 0x282

Seven bytes every 150 ms. **Both stations send their lever positions all the time, whether or not they hold command** [M].

| Byte | Content | Values |
|---|---|---|
| 0 | Flags | Table below |
| 1 | Port gear | FF ahead, 00 neutral, 01 astern [M] |
| 2 | Port throttle | 00 to 64 hex = 0 to 100 %. Normally 00 when the gear byte is 00; 3 frames in capture 3 carried 2 to 7 % with gear 00 while a lever moved fast through neutral [M] |
| 3 | Unused | Always 00 [M] |
| 4 | Starboard gear | As byte 1 |
| 5 | Starboard throttle | As byte 2 |
| 6 | Unused | Always 00 [M] |

Ahead was labelled in capture 2 ("both together ahead"), astern in capture 3 ("port astern fast") [M]. An early guess had them the other way round; it is corrected everywhere in this repository.

### Byte 0 flags

| Bit | Meaning | Behaviour [M] |
|---|---|---|
| 0x40 | Always set | Every station frame |
| 0x01 | This station has command | Only one station at a time |
| 0x02 | Warm-up: gear inhibited, throttle live | System-wide. Set at every power-on. The other station mirrors a change 140 to 160 ms later |
| 0x08 | Synchronisation | System-wide, mirrored like 0x02 |
| 0x04 | Held | Description held pending disclosure to the manufacturers |
| 0x10, 0x20, 0x80 | Never seen set | |

Common values: 42 = warm-up, not in command (state after power-on); 43 = in command, warm-up on; 41 = in command, normal.

## 5. Actuator status, 0x384 and 0x485

One byte every 153.6 ms. It reports what the gearbox is doing, not what the lever asks for.

| Value | Meaning |
|---|---|
| C0 | Neutral [M] |
| 4C | Shifting, cable moving [M]. Usually one frame, sometimes two |
| 44 | Ahead engaged [M] |
| 48 | Astern engaged [M] |
| 40 | Booting, before the first C0 [M] |

A reversal reads 44, 4C, C0, 4C, 48. Bit reading [I]: 0x80 neutral, 0x04 ahead, 0x08 astern, 0x40 always set.

## 6. Boot sequence

Capture 2, two power-ons, identical to within 1 ms [M]. t = 0 at the first frame.

| t (ms) | Frame |
|---|---|
| 0 | 0x705#00, 0x704#00 (actuator boot-up), 0x384#40, 0x485#40 |
| 255 | 0x282#42, flybridge first frame |
| 265 | 0x181#42, main helm first frame |
| 512 | 0x705#05, 0x704#05 |
| 925 | 0x702#05, first flybridge heartbeat |
| 955 | 0x701#05, first main helm heartbeat |
| 1076 | 0x384#C0, 0x485#C0, actuators in neutral |

- No NMT start, SDO or SYNC. Every node starts by itself [M].
- The stations never send a CANopen boot-up 00. Their first heartbeat is already 05, about 670 ms after their first station frame [M].
- With Fast Start-up Mode off, nobody holds command after power-on. Flags stay 42 until Command is held at one head [M].

## 7. Command and modes

All keypad actions are 1.5 s holds with both levers in neutral [Manual]. The head has four buttons: Engine P, Command, Warm/Sync, Engine S.

- **Taking command with nobody in command** (after power-on): holding Command changes that head's flags from 42 to 43 in one frame [M].
- **Moving command between stations:** not documented in this release; disclosure to the manufacturers comes first.
- **Warm-up:** throttle only, gear inhibited. Levers to 100 % throttle left both actuators at C0 [M]. Warm-up switched at either head sets the flag on both [M].
- **Synchronisation:** the head in command writes its right lever into both the port and starboard bytes, and both actuators follow it [M]. The left lever is assumed ignored; the captures cannot show which lever was moved [I]. Sync was refused while warm-up was on: flags stayed 43 [M]. The manual's 10 % RPM condition cannot explain that with the engines stopped.

## 8. Shift timing

Engines off. Seconds from the lever frame (first station frame with the new gear byte) to the actuator frames. Every event is in `data/reference/06-shift-events.csv`.

| Case | Events | First 4C | Final code, min to max (mean) |
|---|---|---|---|
| Engage ahead from neutral | 31 | 0.33 to 0.47 s | 0.45 to 0.69 s (0.56) |
| Engage astern from neutral | 5 | 0.34 to 0.41 s | 0.34 to 0.57 s (0.45) |
| Disengage, throttle at idle | 10 | 0.28 to 0.36 s | 0.33 to 0.51 s (0.42) |
| Disengage, throttle above 5 % | 26 | 0.24 to 0.71 s | 0.29 to 0.86 s (0.51) |

**Fast reversals, ahead to astern (capture 3) [M]:**

| Case | Lever leaves gear to C0 | C0 to opposite gear | Total |
|---|---|---|---|
| Port, ahead at idle, straight through | 0.54 s | 0.46 s | 1.00 s |
| Starboard, ahead at 45 %, straight through | 0.80 s | 0.61 s | 1.42 s |
| Port, ahead at 21 to 31 %, 1 s pause in neutral | 0.86 s | 0.61 s | 1.48 s |
| Port, ahead at 41 %, straight through | 0.98 s | 0.46 s | 1.44 s |

- The EC4 adds no neutral dwell of its own: consistent with the shift delays dI and dA both at their factory default of 0.0 s [M, Manual].
- The actuator returns the throttle to idle before it shifts. The station frame already shows gear 00 with the throttle at or near 00, so the extra time is inside the actuator: about 0.4 s when the throttle was above about 20 % [M].
- With the engines running, propeller and RPM decay may lag the mechanism. These are mechanical minimums, not safe reversal times under way.
- For anyone building a monitor: allow at least about 0.85 s for the first status change when the throttle was not at idle, about 0.5 s when it was.

## 9. A lesson for tap builders: frames lost at the sniffer

Capture 2 missed 73 frames, 68 of them from the port actuator, all during starboard-only activity, with no late retransmissions [M]. The cause was the sniffer, not the bus: its CAN_L input was open circuit after a terminal repair lifted a pad. It received on CAN_H alone with about 0.1 V of margin over the ISO1050 dominant threshold, so one node's slightly low dominant level dropped below it [M, I]. After a wire repair, capture 3 lost nothing over 578 s and the bus error count stayed flat [M].

Check continuity from the connector pins to the transceiver pins of any tap, and meter CAN_H to CAN_L before trusting a capture.

## 10. Open

- Reversal times with the engines running.
- Sync with warm-up off after a refused attempt; left lever moved alone in sync.
- Flybridge astern: never captured with the flybridge in command. Expected 01 and 48 as at the main helm [I].
- Both levers astern together: never captured.
- Trim buttons and actuator display codes (FI, CC).
- Behaviour when the station in command goes silent.
- Further items are held pending disclosure.
