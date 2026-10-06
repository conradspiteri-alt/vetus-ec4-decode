#!/usr/bin/env python3
"""Measure every timing and protocol number used by docs/10-Station3-Protocol-Spec.md.

Usage:
    python3 log_stats.py [--json out.json] LOG [LOG ...]

Default logs: ../captures/capture1.log and capture3.log relative to this file.
Prints a plain-text report. Each section name matches the [M] references in the spec.
Standard library only.
"""
import argparse
import json
import os
import statistics as st
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from candump_io import read_log, backlog_end  # noqa: E402

PERIOD = {0x181: 0.150, 0x282: 0.150, 0x384: 0.1536, 0x485: 0.1536,
          0x701: 0.500, 0x702: 0.500, 0x704: 0.512, 0x705: 0.512}
STATIONS = {0x181: 'main', 0x282: 'fly'}
ACT = {0x384: 'port', 0x485: 'stbd'}
POWER_GAP_S = 5.0
F_CMD, F_WARM, F_SYNC, F_ALWAYS = 0x01, 0x02, 0x08, 0x40


def pct(xs, p):
    if not xs:
        return None
    xs = sorted(xs)
    k = (len(xs) - 1) * p / 100.0
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def summ(xs, scale=1000.0, nd=3):
    if not xs:
        return None
    return {'n': len(xs), 'mean': round(st.mean(xs) * scale, nd), 'median': round(st.median(xs) * scale, nd),
            'sd': round((st.pstdev(xs) if len(xs) > 1 else 0) * scale, nd),
            'min': round(min(xs) * scale, nd), 'p0.1': round(pct(xs, 0.1) * scale, nd),
            'p99.9': round(pct(xs, 99.9) * scale, nd), 'max': round(max(xs) * scale, nd)}


def analyse(path):
    frames, notes, bad = read_log(path)
    name = os.path.basename(path)
    R = {'file': name, 'frames': len(frames), 'notes': len(notes), 'bad_lines': len(bad)}
    bl = backlog_end(frames)
    R['backlog_end_s'] = bl
    good = [f for f in frames if bl is None or f.t > bl]

    # ---- inventory ----
    inv = {}
    for f in frames:
        d = inv.setdefault('0x%03X' % f.id, {'count': 0, 'dlc': set(), 'ext': f.ext, 'values': set()})
        d['count'] += 1
        d['dlc'].add(len(f.data))
        if len(d['values']) < 40:
            d['values'].add(f.hex)
    for k, d in inv.items():
        d['dlc'] = sorted(d['dlc'])
        d['values'] = sorted(d['values']) if len(d['values']) < 40 else '40+ distinct'
    R['inventory'] = inv
    t0, t1 = frames[0].t, frames[-1].t
    R['span_s'] = round(t1 - t0, 3)

    # ---- invariants of station frames ----
    flags_seen, gear_seen, thr_max, res_nonzero = {}, set(), 0, 0
    thr_in_neutral_nowarm = 0
    for f in frames:
        if f.id in STATIONS:
            d = f.data
            flags_seen.setdefault(STATIONS[f.id], set()).add('%02X' % d[0])
            gear_seen.update(('%02X' % d[1], '%02X' % d[4]))
            thr_max = max(thr_max, d[2], d[5])
            if d[3] or d[6]:
                res_nonzero += 1
            if not (d[0] & F_WARM) and ((d[1] == 0 and d[2]) or (d[4] == 0 and d[5])):
                thr_in_neutral_nowarm += 1
    R['station_flags_seen'] = {k: sorted(v) for k, v in flags_seen.items()}
    R['station_gear_values'] = sorted(gear_seen)
    R['station_throttle_max'] = thr_max
    R['station_bytes3_6_nonzero_frames'] = res_nonzero
    R['station_frames_neutral_gear_with_throttle_outside_warmup'] = thr_in_neutral_nowarm
    R['actuator_values'] = sorted({'%02X' % f.data[0] for f in frames if f.id in ACT})
    R['heartbeat_values'] = sorted({'0x%03X#%02X' % (f.id, f.data[0]) for f in frames if 0x700 < f.id < 0x780})

    # ---- periods, jitter, gaps ----
    per, gaps = {}, {}
    last = {}
    for f in good:
        p = PERIOD.get(f.id)
        if not p:
            continue
        if f.id in last:
            dt = f.t - last[f.id]
            if dt < 1.5 * p:
                per.setdefault(f.id, []).append(dt)
            elif dt < POWER_GAP_S:
                gaps.setdefault(f.id, []).append((last[f.id], f.t, dt, round(dt / p) - 1))
        last[f.id] = f.t
    R['periods_ms'] = {'0x%03X' % k: summ(v) for k, v in sorted(per.items())}
    gsum = {}
    for k, v in sorted(gaps.items()):
        gsum['0x%03X' % k] = {'gaps': len(v), 'missed_frames': sum(x[3] for x in v),
                              'max_gap_ms': round(max(x[2] for x in v) * 1000, 1),
                              'gap_hist_missed': {str(m): sum(1 for x in v if x[3] == m) for m in sorted({x[3] for x in v})}}
    R['gaps'] = gsum
    R['missed_total'] = sum(g['missed_frames'] for g in gsum.values())
    R['power_gaps_s'] = [round(b.t - a.t, 3) for a, b in zip(frames, frames[1:]) if b.t - a.t >= POWER_GAP_S]

    # long-term period from continuous runs (clock accuracy relative to the sniffer)
    lt = {}
    for cid in (0x181, 0x282, 0x384, 0x485):
        ts = [f.t for f in good if f.id == cid]
        runs, cur = [], [ts[0]] if ts else []
        for a, b in zip(ts, ts[1:]):
            if b - a > POWER_GAP_S:
                runs.append(cur)
                cur = []
            cur.append(b)
        if cur:
            runs.append(cur)
        best = max(runs, key=lambda r: r[-1] - r[0]) if runs else []
        if len(best) > 10:
            n = round((best[-1] - best[0]) / PERIOD[cid])
            lt['0x%03X' % cid] = {'span_s': round(best[-1] - best[0], 1), 'periods': n,
                                  'period_ms': round((best[-1] - best[0]) / n * 1000, 5),
                                  'ppm_vs_nominal': round(((best[-1] - best[0]) / n / PERIOD[cid] - 1) * 1e6, 1)}
    R['long_term_period'] = lt

    # ---- phase between the two stations and between the actuators ----
    def phase(a_id, b_id, lim):
        out = []
        last_a = None
        for f in good:
            if f.id == a_id:
                last_a = f.t
            elif f.id == b_id and last_a is not None and 0 <= f.t - last_a < lim:
                out.append((f.t, f.t - last_a))
        return out
    ph = phase(0x282, 0x181, 0.075)
    if ph:
        offs = [x[1] for x in ph]
        # drift: offset at the start vs end of each power run
        R['phase_0x282_to_0x181_ms'] = summ(offs)
        firsts = [x for x in ph if x[0] < ph[0][0] + 30]
        lasts = [x for x in ph if x[0] > ph[-1][0] - 30]
        R['phase_0x282_to_0x181_drift'] = {'first30s_median_ms': round(st.median(x[1] for x in firsts) * 1000, 3),
                                           'last30s_median_ms': round(st.median(x[1] for x in lasts) * 1000, 3)}
        # the phase restarts at every power-up; report it per power run, with a least-squares slope
        runs, cur = [], [ph[0]]
        for a, b in zip(ph, ph[1:]):
            if b[0] - a[0] > POWER_GAP_S:
                runs.append(cur)
                cur = []
            cur.append(b)
        runs.append(cur)
        per_run = []
        for r in runs:
            if len(r) < 50:
                continue
            mt = st.mean(x[0] for x in r)
            mo = st.mean(x[1] for x in r)
            slope = sum((x[0] - mt) * (x[1] - mo) for x in r) / sum((x[0] - mt) ** 2 for x in r)
            per_run.append({'start_s': round(r[0][0], 1), 'end_s': round(r[-1][0], 1),
                            'first20_mean_ms': round(st.mean(x[1] for x in r[:20]) * 1000, 3),
                            'last20_mean_ms': round(st.mean(x[1] for x in r[-20:]) * 1000, 3),
                            'drift_ppm': round(slope * 1e6, 2)})
        R['phase_0x282_to_0x181_per_power_run'] = per_run
    pa = phase(0x485, 0x384, 0.075)
    if pa:
        R['phase_0x485_to_0x384_ms'] = summ([x[1] for x in pa])

    # ---- flags events: command taken, warm-up and sync mirroring ----
    st_frames = {1: [], 2: []}
    for f in good:
        if f.id == 0x181:
            st_frames[1].append(f)
        elif f.id == 0x282:
            st_frames[2].append(f)
    merged = sorted([(f.t, 1, f) for f in st_frames[1]] + [(f.t, 2, f) for f in st_frames[2]], key=lambda x: x[0])
    latest = {1: None, 2: None}
    command_set, mirror = [], []
    prev = {1: None, 2: None}
    pending_bit = {}
    for t, s, f in merged:
        o = 3 - s
        fl = f.data[0]
        pf = prev[s]
        if pf is not None and t - pf.t > POWER_GAP_S:
            pf = None
        if pf is not None:
            pfl = pf.data[0]
            if (fl & F_CMD) and not (pfl & F_CMD):
                command_set.append({'t': t, 'station': s, 'flags_before': '%02X' % pfl, 'flags_after': '%02X' % fl})
            for bit in (F_WARM, F_SYNC):
                if (fl ^ pfl) & bit:
                    key = (bit, bool(fl & bit))
                    if key in pending_bit and pending_bit[key][1] == o and t - pending_bit[key][0] < 1.0:
                        t_a, s_a, a_cmd = pending_bit.pop(key)
                        mirror.append({'bit': 'warm' if bit == F_WARM else 'sync', 'on': key[1], 't': round(t_a, 3),
                                       'initiator': 'main' if s_a == 1 else 'fly', 'initiator_had_cmd': a_cmd,
                                       'mirror_delay_ms': round((t - t_a) * 1000, 1)})
                    else:
                        pending_bit[key] = (t, s, bool(fl & F_CMD))
        latest[s] = f
        prev[s] = f
    R['command_set'] = command_set
    R['unmatched_bit_changes'] = [{'bit': 'warm' if k[0] == F_WARM else 'sync', 'on': k[1], 't': round(v[0], 3),
                                   'station': v[1]} for k, v in pending_bit.items()]
    R['mirror'] = mirror

    # ---- lever gear change at the commanding station -> actuator response ----
    act = {0x384: [], 0x485: []}
    for f in good:
        if f.id in act:
            act[f.id].append(f)

    def act_after(aid, t, until):
        return [x for x in act[aid] if t < x.t <= until]
    resp = []
    cmd_prev = {}
    for t, s, f in merged:
        d = f.data
        if not (d[0] & F_CMD) or (d[0] & F_WARM):
            cmd_prev.pop(s, None) if not (d[0] & F_CMD) else None
            if d[0] & F_CMD:
                cmd_prev[s] = f
            continue
        pf = cmd_prev.get(s)
        cmd_prev[s] = f
        if pf is None or t - pf.t > 1:
            continue
        for gi, aid in ((1, 0x384), (4, 0x485)):
            if d[gi] != pf.data[gi]:
                target = {0xFF: 0x44, 0x01: 0x48, 0x00: 0xC0}.get(d[gi])
                seq = act_after(aid, t, t + 3.0)
                if not seq:
                    continue
                first_change = next((x for x in seq if x.data[0] != seq[0].data[0] or x.data[0] == 0x4C), None)
                t4c = next((x.t for x in seq if x.data[0] == 0x4C), None)
                tfin = next((x.t for x in seq if x.data[0] == target), None)
                # did the next station frame change the gear again before the final state? (then skip)
                nxt = next((x for x in st_frames[s] if x.t > t and x.data[gi] != d[gi]), None)
                if nxt and tfin and nxt.t < tfin:
                    continue
                vals = []
                for x in seq:
                    if not vals or vals[-1] != x.data[0]:
                        vals.append(x.data[0])
                    if x.t >= (tfin or 0) and tfin:
                        break
                # actuator pipeline (spec 6.7): whole actuator periods from its first frame after the
                # command to the first changed code, and the latest frame that still showed the old code
                fc_idx = seq.index(first_change) if first_change is not None else None
                last_old = seq[fc_idx - 1] if fc_idx else None
                resp.append({'t': round(t, 3), 'station': 'main' if s == 1 else 'fly', 'side': ACT[aid],
                             'from': '%02X' % pf.data[gi], 'to': '%02X' % d[gi], 'target': '%02X' % target if target else None,
                             'act_before': '%02X' % seq[0].data[0],
                             'first_change_periods': round((first_change.t - seq[0].t) / PERIOD[aid], 2) if first_change else None,
                             't_first_change_ms': round((first_change.t - t) * 1000, 1) if first_change else None,
                             't_last_old_code_ms': round((last_old.t - t) * 1000, 1) if last_old else None,
                             't_first_act_frame_ms': round((seq[0].t - t) * 1000, 1),
                             't_4C_ms': round((t4c - t) * 1000, 1) if t4c else None,
                             't_final_ms': round((tfin - t) * 1000, 1) if tfin else None,
                             'sequence': ' '.join('%02X' % v for v in vals)})
    R['gear_response'] = resp
    eng = [r for r in resp if r['to'] in ('FF', '01')]
    dis = [r for r in resp if r['to'] == '00']
    R['gear_response_summary'] = {
        'engage_n': len(eng), 'engage_4C_ms': summ([r['t_4C_ms'] / 1000 for r in eng if r['t_4C_ms'] is not None]),
        'engage_final_ms': summ([r['t_final_ms'] / 1000 for r in eng if r['t_final_ms'] is not None]),
        'engage_without_4C': sum(1 for r in eng if r['t_4C_ms'] is None and r['t_final_ms'] is not None),
        'disengage_n': len(dis), 'disengage_4C_ms': summ([r['t_4C_ms'] / 1000 for r in dis if r['t_4C_ms'] is not None]),
        'disengage_final_ms': summ([r['t_final_ms'] / 1000 for r in dis if r['t_final_ms'] is not None]),
        'disengage_without_4C': sum(1 for r in dis if r['t_4C_ms'] is None and r['t_final_ms'] is not None),
        'no_final_within_3s': sum(1 for r in resp if r['t_final_ms'] is None),
        'engage_first_change_periods': dict(sorted(
            {str(p): sum(1 for r in eng if r['first_change_periods'] == p)
             for p in {r['first_change_periods'] for r in eng}}.items())),
        'first_change_ms_max': max((r['t_first_change_ms'] for r in resp if r['t_first_change_ms'] is not None), default=None),
        'last_old_code_ms_max': max((r['t_last_old_code_ms'] for r in resp if r['t_last_old_code_ms'] is not None), default=None),
    }

    # ---- warm-up enforcement: commander in warm-up with a gear byte set (spec section 3) ----
    wf = [f for f in st_frames[1] + st_frames[2]
          if (f.data[0] & F_CMD) and (f.data[0] & F_WARM) and (f.data[1] or f.data[4])]
    wf.sort(key=lambda f: f.t)
    episodes, cur = [], []
    for f in wf:
        if cur and f.t - cur[-1].t > 1.0:
            episodes.append(cur)
            cur = []
        cur.append(f)
    if cur:
        episodes.append(cur)
    wact = {}
    for ep in episodes:
        for x in act[0x384] + act[0x485]:
            if ep[0].t <= x.t <= ep[-1].t + 0.7:  # 0.7 s covers the worst captured final response (686.4 ms)
                wact['%02X' % x.data[0]] = wact.get('%02X' % x.data[0], 0) + 1
    R['warmup_gear_frames'] = {'station_frames_gear_set': len(wf),
                               'with_throttle_above_0': sum(1 for f in wf if f.data[2] or f.data[5]),
                               'episodes': len(episodes),
                               'actuator_frames_first_to_last_plus_0.7s': wact}

    # ---- context of every port-actuator gap: which commanding levers moved (spec 3, A-08) ----
    gctx = []
    for (ta, tb, dt, missed) in gaps.get(0x384, []):
        cm = [f for f in merged if ta - 1.0 < f[0] < tb + 0.3 and (f[2].data[0] & F_CMD)]
        pv = {(f[2].data[1], f[2].data[2]) for f in cm}
        sv = {(f[2].data[4], f[2].data[5]) for f in cm}
        gctx.append({'t': round(ta, 3), 'gap_ms': round(dt * 1000, 1), 'missed': missed, 'over_400ms': dt > 0.4,
                     'port_lever_states': len(pv), 'port_lever_neutral': pv == {(0, 0)},
                     'stbd_lever_states': len(sv),
                     'stbd_actuator_codes': sorted({'%02X' % x.data[0] for x in act[0x485] if ta - 1.0 < x.t < tb + 0.3})})
    R['port_gap_context'] = gctx
    R['port_gap_summary'] = {'gaps': len(gctx), 'over_400ms': sum(1 for g in gctx if g['over_400ms']),
                             'port_lever_neutral_in_all': all(g['port_lever_neutral'] for g in gctx) if gctx else None,
                             'stbd_lever_moving_in_all': all(g['stbd_lever_states'] > 1 for g in gctx) if gctx else None,
                             'stbd_status_constant_C0': [g['t'] for g in gctx if g['stbd_actuator_codes'] == ['C0']]}

    # ---- the actuators ignore the station without command ----
    ign = 0
    ign_t = []
    lat_act = {0x384: None, 0x485: None}
    lat_st = {1: None, 2: None}
    for f in good:
        if f.id in lat_act:
            lat_act[f.id] = f
        if f.id in (0x181, 0x282):
            lat_st[1 if f.id == 0x181 else 2] = f
        if f.id in lat_act and lat_st[1] and lat_st[2]:
            gi = 1 if f.id == 0x384 else 4
            for s in (1, 2):
                o = 3 - s
                a, b = lat_st[s], lat_st[o]
                if not (a.data[0] & F_CMD) and (b.data[0] & F_CMD) and a.data[gi] != 0 and b.data[gi] == 0 \
                        and not (b.data[0] & F_SYNC) and f.data[0] == 0xC0:
                    ign += 1
                    ign_t.append(f.t)
    R['actuator_C0_while_noncommander_lever_in_gear'] = {'frames': ign,
                                                         'first_s': round(ign_t[0], 2) if ign_t else None,
                                                         'last_s': round(ign_t[-1], 2) if ign_t else None}

    # ---- lever/actuator correlation (for astern 01/48) ----
    corr = {}
    for f in good:
        if f.id in lat_act:
            lat_act[f.id] = f
        if f.id == 0x181:
            lat_st[1] = f
        if f.id in lat_act and lat_st[1] and (lat_st[1].data[0] & F_CMD):
            gi = 1 if f.id == 0x384 else 4
            key = '%02X->%02X' % (lat_st[1].data[gi], f.data[0])
            corr[key] = corr.get(key, 0) + 1
    R['main_cmd_gear_vs_actuator_frames'] = corr

    # ---- boot sequences ----
    boots = []
    starts = [frames[0]] + [b for a, b in zip(frames, frames[1:]) if b.t - a.t >= POWER_GAP_S]
    for s0 in starts:
        seq = [f for f in frames if s0.t <= f.t < s0.t + 1.6]
        if not any(f.id in (0x704, 0x705) and f.data[:1] == b'\x00' for f in seq) and \
                not any(f.id in ACT and f.data[:1] == b'\x40' for f in seq):
            continue
        firsts = {}
        for f in seq:
            k = '0x%03X#%s' % (f.id, f.hex)
            if k not in firsts:
                firsts[k] = round((f.t - s0.t) * 1000, 1)
        st_first = {c: next((round((f.t - s0.t) * 1000, 1) for f in seq if f.id == c), None) for c in (0x181, 0x282)}
        hb_first = {c: next((round((f.t - s0.t) * 1000, 1) for f in seq if f.id == c), None) for c in (0x701, 0x702)}
        boots.append({'t0': s0.t, 'first_of_each': firsts, 'station_tpdo_first_ms': st_first,
                      'station_hb_first_ms': hb_first})
    R['boots'] = boots

    # ---- bus load ----
    bits = 0
    for f in good:
        n = len(f.data)
        base = 44 + 8 * n + 3  # SOF..EOF + IFS, 11-bit id
        bits += base
    span = good[-1].t - good[0].t - sum(R['power_gaps_s'])
    R['bus_load_pct_unstuffed'] = round(bits / span / 125000 * 100, 2)
    R['bus_load_pct_worst_stuff'] = round(bits * 1.2 / span / 125000 * 100, 2)

    # notes with 'bus error'
    R['bus_error_notes'] = sum(1 for n in notes if 'bus error' in n[1].lower())
    return R


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    dflt = [os.path.join(here, '..', 'captures', n) for n in ('capture1.log', 'capture3.log')]
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('logs', nargs='*', default=dflt)
    ap.add_argument('--json', help='write the full result as JSON here')
    a = ap.parse_args()
    out = {}
    for p in a.logs:
        R = analyse(p)
        out[R['file']] = R
        print('=' * 78)
        print(R['file'])
        for k, v in R.items():
            if k in ('gear_response',):
                continue
            print('%s: %s' % (k, json.dumps(v, default=list)))
    if a.json:
        with open(a.json, 'w') as fh:
            json.dump(out, fh, indent=1, default=list)
    return 0


if __name__ == '__main__':
    sys.exit(main())
