#!/usr/bin/env python3
"""Validate dbc/ec4.dbc against the capture logs in captures/.

Checks, for every frame of every log:
  1. The ID is defined in the DBC (no unknown traffic).
  2. The DLC equals the DBC length.
  3. cantools decodes it with strict range checking (decode_choices off, scaling on).
  4. Every enumerated field (gear, actuator state, NMT state) is a defined choice.
  5. Station invariants: Flag_Always1 = 1, unknown flag bits = 0, reserved bytes = 0, throttle <= 100.
  6. Round trip: encode(decode(frame)) reproduces the original bytes exactly.

Usage: python3 validate_dbc.py [--dbc PATH] [LOG ...]
Exit status 0 when every check passes, 1 otherwise.
"""
import argparse
import os
import sys
from collections import Counter, defaultdict

import cantools

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candump_io import read_log  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
DEF_DBC = os.path.join(HERE, '..', 'dbc', 'ec4.dbc')
DEF_LOGS = [os.path.join(HERE, '..', 'captures', n) for n in ('capture1.log', 'capture3.log')]
PROPOSED = set()
STATION_IDS = {0x181, 0x282}
ACT_IDS = {0x384, 0x485}


def choices_of(msg, sig):
    s = msg.get_signal_by_name(sig)
    return {int(k) for k in (s.choices or {})}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dbc', default=DEF_DBC)
    ap.add_argument('logs', nargs='*', default=DEF_LOGS)
    a = ap.parse_args()

    db = cantools.database.load_file(a.dbc, strict=True)
    by_id = {m.frame_id: m for m in db.messages}
    errors = []
    print('DBC: %s, %d messages' % (os.path.basename(a.dbc), len(db.messages)))
    for m in db.messages:
        tag = ' (PROPOSED)' if m.frame_id in PROPOSED else ''
        print('  0x%03X %-32s dlc %d, %d signals, cycle %s ms%s' % (
            m.frame_id, m.name, m.length, len(m.signals), m.cycle_time, tag))
    for pid in PROPOSED:
        if pid not in by_id or 'PROPOSED' not in by_id[pid].name:
            errors.append('proposed message 0x%03X missing or not marked PROPOSED' % pid)

    for path in a.logs:
        frames, notes, bad = read_log(path)
        name = os.path.basename(path)
        per_id = Counter()
        values = defaultdict(Counter)
        unknown = Counter()
        if bad:
            errors.append('%s: %d unparseable lines, first at line %d' % (name, len(bad), bad[0]))
        for f in frames:
            if f.ext or f.rtr:
                errors.append('%s line %d: extended or RTR frame' % (name, f.line))
                continue
            if f.id in PROPOSED:
                errors.append('%s line %d: proposed station-3 ID 0x%03X seen on the bus' % (name, f.line, f.id))
            m = by_id.get(f.id)
            if m is None:
                unknown[f.id] += 1
                continue
            per_id[f.id] += 1
            if len(f.data) != m.length:
                errors.append('%s line %d: 0x%03X DLC %d, DBC %d' % (name, f.line, f.id, len(f.data), m.length))
                continue
            try:
                d = m.decode(f.data, decode_choices=False, scaling=True)
            except Exception as e:  # strict range check failure lands here
                errors.append('%s line %d: 0x%03X decode failed: %s' % (name, f.line, f.id, e))
                continue
            # round trip
            try:
                enc = m.encode(d, scaling=True, strict=True)
            except Exception as e:
                errors.append('%s line %d: 0x%03X encode failed: %s' % (name, f.line, f.id, e))
                continue
            if bytes(enc) != f.data:
                errors.append('%s line %d: 0x%03X round trip %s != %s' % (name, f.line, f.id, bytes(enc).hex(), f.data.hex()))
            if f.id in STATION_IDS:
                for g in ('GearPort', 'GearStbd'):
                    values[(f.id, g)][d[g]] += 1
                    if d[g] not in choices_of(m, g):
                        errors.append('%s line %d: 0x%03X %s=0x%02X not a defined gear code' % (name, f.line, f.id, g, d[g]))
                for t in ('ThrottlePort', 'ThrottleStbd'):
                    if d[t] > 100:
                        errors.append('%s line %d: throttle %d > 100' % (name, f.line, d[t]))
                if d['Flag_Always1'] != 1 or d['Flag_Unknown4_5'] or d['Flag_Unknown7']:
                    errors.append('%s line %d: 0x%03X unexpected flag bits 0x%02X' % (name, f.line, f.id, f.data[0]))
                if d['Reserved3'] or d['Reserved6']:
                    errors.append('%s line %d: 0x%03X reserved byte not zero' % (name, f.line, f.id))
                values[(f.id, 'flags')]['%02X' % f.data[0]] += 1
            elif f.id in ACT_IDS:
                values[(f.id, 'ActuatorState')]['%02X' % d['ActuatorState']] += 1
                if d['ActuatorState'] not in choices_of(m, 'ActuatorState'):
                    errors.append('%s line %d: 0x%03X state 0x%02X undefined' % (name, f.line, f.id, d['ActuatorState']))
            else:
                values[(f.id, 'NmtState')]['%02X' % d['NmtState']] += 1
                if d['NmtState'] not in choices_of(m, 'NmtState') or d['NmtToggle']:
                    errors.append('%s line %d: 0x%03X heartbeat 0x%02X undefined' % (name, f.line, f.id, f.data[0]))
        print('\n%s: %d frames, %d notes, %d decoded, %d unknown-ID frames' % (
            name, len(frames), len(notes), sum(per_id.values()), sum(unknown.values())))
        for i in sorted(per_id):
            print('  0x%03X %-32s %6d' % (i, by_id[i].name, per_id[i]))
        for k in sorted(values):
            print('  0x%03X %-13s %s' % (k[0], k[1], dict(sorted(values[k].items(), key=lambda kv: str(kv[0])))))
        for i, n in unknown.items():
            errors.append('%s: %d frames of undefined ID 0x%03X' % (name, n, i))

    print()
    if errors:
        print('FAIL: %d problems' % len(errors))
        for e in errors[:50]:
            print('  ' + e)
        return 1
    print('PASS: every frame decoded, every value defined, every round trip exact.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
