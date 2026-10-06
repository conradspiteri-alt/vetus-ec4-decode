# EC4 capture 3: frame-loss confirmation and fast shift

Written 2 Oct 2026. Phone only, sniffer firmware rev D.2 (no laptop needed). Rev D.2 counts bus errors but does not timestamp them, so the error count is read from the status page at the start and end of each block and typed into a note.

Goals:
1. Confirm the CAN_L repair: starboard-only activity must lose no port-actuator frames and add no bus errors.
2. Fast-shift test L4-10: label astern (closes the 01 and 48 codes), measure actuator transition times, confirm the EC4 passes a fast reversal straight through (dI = dA = 0.0 s).

Never change DIP switches, JP14 or JP19.

## 0. Before connecting (multimeter, EC4 off)
- Sniffer unplugged: CAN_H to CAN_L on the board must not be a short; CAN_L to GND must not be a short.
- Splitter plugged in, EC4 off: about 67 ohm across CAN_H and CAN_L at the drop, as before. About 40 ohm means a terminator has appeared.

## 1. Start
1. Sniffer on, EC4 off. Status: listening, frames 0, bus errors 0.
2. Note `boot: EC4 power on`, then switch the EC4 on. Status: locked 125000.
3. Main helm: hold Command, then Warm/Sync off. Note `errors N` with the status count.

## 2. Block A: frame-loss check (starboard only)
1. Note `A start errors N`.
2. Starboard lever: ahead detent 5 s, neutral 5 s. Three times.
3. Starboard lever: ahead, throttle to about 50 % and back, neutral. Twice.
4. Note `A end errors N`.

Pass: the count does not change; the log shows no port-actuator gaps.

## 3. Block B: fast shift (engines off)
Note each step before doing it.
1. `port ahead`: port lever to the ahead detent, hold 5 s.
2. `port astern fast`: straight through neutral to the astern detent in one movement, hold 5 s.
3. `port neutral`.
4. Repeat 1 to 3 for starboard (`stbd ahead`, `stbd astern fast`, `stbd neutral`).
5. Both levers together: `both ahead`, `both astern fast`, `both neutral`.
6. Astern to ahead: `port astern`, `port ahead fast`, `port neutral`; then starboard the same.
7. With a pause: `port ahead`, then `port pause 1s` (lever in neutral for one second), then `port astern`, `port neutral`.
8. Note `B end errors N`.

## 4. Optional
- Actuator displays: read dI and dA only if you know the menu path; change nothing. Note `port dI x dA y`, `stbd dI x dA y`.
- Engines running at idle, lines secure, nobody near the stern: one fast reversal per engine, notes as in block B.

## 5. Finish
Note `step done`, read the final status, roll the file and download the log from the phone page.

## What the results mean
| Observation | Meaning |
|---|---|
| Block A: error count unchanged, no port gaps | CAN_L repair confirmed; the capture-2 loss was the sniffer |
| Block A: errors or port gaps return | A bus-side fault remains: add a second listener at another point |
| Block B: lever byte 01 with actuator 48 after `astern` notes | Astern codes confirmed |
| Actuator time in C0 about equal to lever time in neutral plus travel | The EC4 adds no reversal delay (dI = 0) |
| Fixed time in C0 regardless of lever speed | The EC4 enforces a delay; a third-party controller need add none on top |
| Gear held for a fixed time after the lever reaches neutral | dI is non-zero |
