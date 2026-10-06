# EC4 capture 2: both helms, all modes

Goal: map the sync flag bit, the flybridge (node 2) lever bytes, the boot sequence, and the Engine LED blink when a station is synchronised but not in command.

Node 1 = main helm (confirmed). Node 2 = flybridge (only other station).

Source for every button action: Vetus EC4 manual 030624.13 (2024), sections 3.2 to 3.4.
https://vetus.com/wp-content/uploads/030624.13-r03-2024-10-EC4_EC4HSM-EN.pdf

## Keypad (each head, twin lever)
Four illuminated push-buttons: **Engine P** (green, left), **Command** (red), **Warm/Sync** (amber), **Engine S** (green, right). Trim +/- buttons exist on some heads (flap option). Every action is a **1.5 s hold**. Both levers must be in **neutral** for every mode change.

## Mode procedures
| Action | Levers | Hold 1.5 s | Result |
|---|---|---|---|
| Take command, stationary | Both neutral | Command | Command LED on, Warm/Sync blinking (warm-up) |
| Warm-up off / on | Both neutral | Warm/Sync | Warm/Sync LED off / blinking |
| **Sync on** (right lever drives both engines) | Both neutral | **Engine P + Engine S together** | Warm/Sync and Command LEDs steady |
| Sync off | Both neutral | Engine P + Engine S together | Warm/Sync LED off, each lever drives its own engine |
| Take command under way | Match the commanding station's levers until this head's Engine LEDs blink | Command | Command moves to this head |

Conditions: sync on/off only at the station in command, and only if engine RPMs differ by no more than 10 %. With engines stopped both read 0, so it should be accepted; if it refuses, start both engines and leave them at idle in neutral.

Never change DIP switches, JP14 or JP19.

## Prerequisite: firmware rev D
Test 0 captures the EC4 boot, so the sniffer must be running before the EC4 is powered. Rev D (delivered 23 Sep 2026) listens at 125k from power-up, opens the log at boot, locks on the first frame (note `bitrate locked 125000`), retries WiFi every 30 s and serves the phone note page at http://ec4-can.local/mark. Flash it before the visit and check `s` shows `listening` with the EC4 off.

## Capture sequence (one note per step, phone /mark page or serial `n`)

Test 0: boot sequence
0. Sniffer on and logging, EC4 off. Note `boot: EC4 power on`. Switch the EC4 on. Wait 30 s. Captures boot-up heartbeats (0x7nn#00), any NMT start command (ID 0x000) and any SDO configuration exchange. **This is what a third station must reproduce to join the bus.**

Main helm (node 1)
1. `main: command` - Command
2. `main: warm-up throttle` - warm-up still on: push the port lever past the ahead detent to about 50 %, back, then starboard. Expect throttle bytes to rise with the actuators staying neutral.
3. `main: warm off` - Warm/Sync
4. `main: sync on` - Engine P + Engine S
5. `main: sync right lever` - right lever: ahead detent, sweep to full and back, neutral, astern detent, sweep, neutral
6. `main: sync left lever` - left lever through the same range; expect no effect
7. `main: sync off` - Engine P + Engine S
8. `fly: refused command` - go to the flybridge, put one lever in ahead detent, hold Command. Expect refusal (not neutral, not synchronised). Levers back to neutral.

Flybridge (node 2)
9. `fly: command` - Command
10. `fly: port lever` - port: astern detent, neutral, ahead detent, neutral, ahead sweep, neutral
11. `fly: stbd lever` - starboard, same
12. Repeat steps 3 to 7 with `fly:` notes
13. `fly: warm on` - Warm/Sync

Transfer under way (engines stopped)
14. Flybridge in command, warm-up off, its levers at ahead detent
15. At the main helm, move its levers to ahead detent until its Engine LEDs blink - `main: synced, engine LEDs blinking`
16. Hold Command at the main helm - `main: took command under way`
17. Both helms back to neutral, warm-up on.

Optional, only if fitted
18. `trim` - trim +/- buttons, only if the heads have them and they drive something on the test boat
19. Actuator display: read the firmware version ("FI xx") and the CANBus check ("CC") without changing any parameter - `actuator display`

## Out of scope for capture 2
- Loss of command: removing or de-powering the station in command while in gear. That is Reverse-Engineering-Plan phase 3 and needs the engines immobilised and a separate session.
- Fast Start-up Mode and trolling: both are DIP settings. Not tested.

## Practical note
Use the phone note page (/mark) for markers; its buttons match the notes above. Serial `n` still works with the laptop at the node. If the phone cannot resolve ec4-can.local, use the IP from the hotspot client list.
