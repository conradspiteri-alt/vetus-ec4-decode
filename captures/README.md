# Captures

candump-compatible text logs from the listen-only sniffer (`firmware/sniffer/`). One frame per line: `(seconds since sniffer boot) can0 ID#DATA`. Lines starting `#` are comments and timestamped notes typed on a phone during the capture, for example `# (478.405634) port astern fast`.

| File | Date | Frames | Firmware | Content |
|---|---|---|---|---|
| capture1.log | 23 Sep 2026 | 5,522 | rev C | Main helm only, no notes. The first 0.47 s are a compressed backlog: ignore their timing |
| capture1b.log | 24 or 25 Sep 2026 | 3,868 | rev C | Unlabelled, not used for the decode |
| capture3.log | 2 Oct 2026 | 19,786 | rev D.2 | Starboard-only shifts and labelled fast reversals. Zero frames missed |
| sample/ec4-sample.log | 2 Oct 2026 | 18,356 | rev D.2 | Excerpt of capture3.log, 100 to 640 s: power-on, command taken at the main helm, warm-up off, starboard shifts, labelled fast reversals. The viewer's built-in sample; see `../docs/events.md` |

Capture 2 (27 Sep 2026, both helms, all modes) is not published in this release. Figures quoted from it in the docs and tables are marked capture 2.

Engines off in every capture. Open them in SavvyCAN (File, Load Log File), decode with `../dbc/ec4.dbc`, or use the tools in `../tools/`.
