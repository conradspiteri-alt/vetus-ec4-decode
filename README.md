# vetus-ec4-can

An independent, listen-only decode of the CAN bus inside a **Vetus EC4** electronic engine control (made by Flexball Italiana, 4500 series), plus the isolated sniffer hardware and firmware that captured it.

Version 0.2, October 2026. By Dr.FireFly.

> Listen only. Do not transmit on an engine-control bus. See `NOTICE.md`.

## What is decoded

- 125 kbit/s, 11-bit IDs, CANopen-like, no master. Eight IDs: two station frames (0x181, 0x282), two actuator status bytes (0x384, 0x485), four heartbeats.
- Station frame byte map: flags, gear (FF ahead, 00 neutral, 01 astern) and throttle (0 to 100 %) for each engine. Both heads broadcast their levers at all times; the gearboxes follow the head in command.
- Actuator status: C0 neutral, 4C shifting, 44 ahead, 48 astern, 40 booting.
- Boot sequence, warm-up, synchronisation, and lever-to-gear timing including labelled fast reversals.

Some findings are not in this release: they are being disclosed to the manufacturers first.

New to this? Start with `docs/examples.md`: ahead and astern at each helm, one picture each. Then `docs/protocol.md` for the decode, and `docs/events.md` for a full sequence from power-on to fast reversals.

![Main helm, both levers ahead](docs/images/examples/01-main-helm-ahead.png)

## Layout

| Path | What |
|---|---|
| `docs/examples.md` | Simple examples: ahead and astern at each helm, one annotated picture each |
| `docs/protocol.md` | The decode, with every value tagged measured, inferred or from the manual |
| `docs/events.md` | Event gallery: the sample capture in the viewer at nine key moments |
| `docs/background-research.md` | Desk research before the first capture (sources linked) |
| `docs/capture-procedures/` | Step lists used for captures 2 and 3 |
| `dbc/ec4.dbc` | DBC for SavvyCAN and cantools; every message observed |
| `data/reference/*.csv` | Reference tables: IDs and timing, byte maps, codes, boot, every shift event, reversals, findings, captures |
| `captures/` | candump logs with phone notes, and `sample/ec4-sample.log`, the viewer's built-in sample |
| `tools/` | Log reader, statistics, DBC validator, replay extractor, secrets check, browser playback viewer |
| `firmware/sniffer/` | ESP32-S3 listen-only logger firmware. Edit `secrets.h` before flashing |
| `hardware/sniffer/` | Carrier PCB (KiCad, gerbers), enclosure (OpenSCAD, STL, drawings), wiring diagrams, full BOM including the Vetus CANT T-piece |

## Viewer

Open `tools/lever-playback/dist/EC4-Lever-Playback.html` after building it, or build it with `python3 tools/lever-playback/build.py`. It opens on the sample capture; load any sniffer log with "Open log file".

## Quick checks

```
pip install cantools
python3 tools/validate_dbc.py                       # decodes the published captures with the DBC
python3 tools/log_stats.py                          # periods, boots, gear response, bus load
python3 hardware/sniffer/tools/check_netlist.py     # PCB nets against the firmware pin map
python3 tools/check_secrets.py                      # run before every commit
python3 tools/lever-playback/build.py               # builds dist/EC4-Lever-Playback.html with the sample built in
python3 tools/lever-playback/screenshots.py         # regenerates docs/images/events (needs Playwright)
```

## Installation the data comes from

A Fairline Phantom 42, twin Volvo Penta TAMD63P, owner-installed EC4 with every parameter at factory default, two twin-lever heads (main helm and flybridge), two actuator boxes. Engines off in every capture.

## Licence

Code: MIT (`LICENSE`). Documentation, data and hardware design files: CC BY 4.0 (`LICENSE-DOCS.md`). Dr.FireFly, 2026.

## Contributing captures

Captures from other EC4 installations are the most useful contribution: one labelled step per note, engines off, listen-only. The procedures in `docs/capture-procedures/` are a template.
