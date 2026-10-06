#!/usr/bin/env python3
"""Turn a EC4 sniffer candump log into a compact replay trace for the firmware host tests.

CSV output (default), one frame per line, time-ordered, stable for equal times:

    # ec4-trace v1 | source capture2.log | frames 45520 | notes 37 | t0_us 0
    t_us,id,dlc,data
    147815760,705,1,00
    147969441,485,1,40
    # note 293289213 main: command

- t_us: integer microseconds of log time (minus t0_us when --rebase is given).
- id:   11-bit identifier, hex, no prefix.
- dlc:  payload length 0..8.
- data: payload hex, upper case, no separators; empty for DLC 0.
- Lines starting with '#' are comments. '# note <t_us> <text>' carries the phone notes.
The C++ reader in the firmware tests skips every '#' line except '# note'.

JSON output (--json): {"source":..., "t0_us":..., "frames":[[t_us, id, "data"], ...], "notes":[[t_us, "text"], ...]}

Usage:
    replay_extract.py LOG [-o OUT] [--json] [--rebase] [--from S] [--to S] [--ids 181,282,...] [--no-notes]
Exit status 1 on unparseable lines, extended or RTR frames (none are expected on the EC4 bus).
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candump_io import read_log  # noqa: E402


def to_us(t):
    return int(round(t * 1e6))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('log')
    ap.add_argument('-o', '--out', help='output file (default: stdout)')
    ap.add_argument('--json', action='store_true', help='write JSON instead of CSV')
    ap.add_argument('--rebase', action='store_true', help='subtract the first frame time so the trace starts at 0')
    ap.add_argument('--from', dest='t_from', type=float, help='first log time to include, seconds')
    ap.add_argument('--to', dest='t_to', type=float, help='last log time to include, seconds')
    ap.add_argument('--ids', help='comma-separated hex IDs to keep, e.g. 181,282,384,485')
    ap.add_argument('--no-notes', action='store_true')
    a = ap.parse_args()

    frames, notes, bad = read_log(a.log)
    problems = []
    if bad:
        problems.append('%d unparseable lines (first %d)' % (len(bad), bad[0]))
    keep = {int(x, 16) for x in a.ids.split(',')} if a.ids else None
    rows = []
    for idx, f in enumerate(frames):
        if f.ext or f.rtr:
            problems.append('line %d: extended or RTR frame' % f.line)
            continue
        if a.t_from is not None and f.t < a.t_from:
            continue
        if a.t_to is not None and f.t > a.t_to:
            continue
        if keep is not None and f.id not in keep:
            continue
        rows.append((to_us(f.t), idx, f.id, f.data))
    rows.sort(key=lambda r: (r[0], r[1]))  # stable time order; the sniffer writes in order already
    nts = [] if a.no_notes else [(to_us(t), txt) for t, txt, _ in notes
                                 if (a.t_from is None or t >= a.t_from) and (a.t_to is None or t <= a.t_to)]
    nts.sort(key=lambda n: n[0])
    t0 = rows[0][0] if (a.rebase and rows) else 0
    src = os.path.basename(a.log)

    out = open(a.out, 'w', newline='\n') if a.out else sys.stdout
    try:
        if a.json:
            json.dump({'format': 'ec4-trace v1', 'source': src, 't0_us': t0,
                       'frames': [[r[0] - t0, r[2], r[3].hex().upper()] for r in rows],
                       'notes': [[t - t0, txt] for t, txt in nts]}, out, separators=(',', ':'))
            out.write('\n')
        else:
            out.write('# ec4-trace v1 | source %s | frames %d | notes %d | t0_us %d\n' % (src, len(rows), len(nts), t0))
            out.write('t_us,id,dlc,data\n')
            # merge notes into the time order; a note goes after frames with the same timestamp
            ni = 0
            for r in rows:
                while ni < len(nts) and nts[ni][0] < r[0]:
                    out.write('# note %d %s\n' % (nts[ni][0] - t0, nts[ni][1].replace('\n', ' ')))
                    ni += 1
                out.write('%d,%X,%d,%s\n' % (r[0] - t0, r[2], len(r[3]), r[3].hex().upper()))
            for t, txt in nts[ni:]:
                out.write('# note %d %s\n' % (t - t0, txt))
    finally:
        if a.out:
            out.close()
    sys.stderr.write('%s: %d frames, %d notes written%s\n' % (src, len(rows), len(nts), (' to ' + a.out) if a.out else ''))
    for p in problems:
        sys.stderr.write('problem: %s\n' % p)
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
