/* EC4 decoder - turns a ec4 sniffer candump log into a playback model.
   Works in the browser (global EC4Decode) and in Node (module.exports).
   Every protocol assumption lives in MAP / constants below so it can be corrected
   in one place as the decode firms up. */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.EC4Decode = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // ---- protocol map (captures capture1 23 Sep and capture2 27 Sep 2026, 125 kbit/s, CANopen-like) ----
  const MAP = {
    // station TPDOs, 150 ms, 7 bytes: [flags, gearPort, thrPort, 0, gearStbd, thrStbd, 0]
    stations: { 1: { id: 0x181, name: 'Main helm', short: 'Main' }, 2: { id: 0x282, name: 'Flybridge', short: 'Fly' } },
    leverPdo: 0x181,          // kept for callers of v1
    station2Pdo: 0x282,
    actA: 0x384,              // node 4 TPDO3: 1 byte gear feedback, follows lever A
    actB: 0x485,              // node 5 TPDO4: 1 byte gear feedback, follows lever B
    flagCommand: 0x01,        // station has command (confirmed 23 Sep)
    flagWarm: 0x02,           // warm-up: gear inhibited, system-wide, mirrored by both stations (confirmed)
    flagSync: 0x08,           // synchronisation, system-wide, mirrored by both stations (27 Sep)
    // gear byte: FF = ahead, 01 = astern (27 Sep: FF labelled "ahead" at the helm; v1 had these inverted)
    aheadSign: -1,
  };
  const HB_LOST_S = 1.6;      // 3 x the slowest heartbeat period (512 ms)
  const BUTTON_HOLD_S = 1.5;  // Vetus/Flexball: Command and Warm/Sync are held 1.5 s
  const DETENT = 0.2;         // lever travel fraction at the gear detent
  const INTERP_MAX_S = 0.5;   // interpolate lever between frames closer than this
  // expected periods, for missed-frame detection (measured, capture 2)
  const PERIOD = { 0x181: 0.150, 0x282: 0.150, 0x384: 0.1536, 0x485: 0.1536, 0x701: 0.5, 0x702: 0.5, 0x704: 0.512, 0x705: 0.512 };
  const ID_NAME = { 0x181: 'main helm 0x181', 0x282: 'flybridge 0x282', 0x384: 'port actuator 0x384', 0x485: 'starboard actuator 0x485',
                    0x701: 'main helm heartbeat', 0x702: 'flybridge heartbeat', 0x704: 'port actuator heartbeat', 0x705: 'starboard actuator heartbeat' };
  const MISS_MAX_S = 5;       // longer silences are power cycles, not missed frames
  const NMT = { 0x00: 'Boot-up', 0x04: 'Stopped', 0x05: 'Operational', 0x7F: 'Pre-operational' };

  const int8 = (b) => (b > 127 ? b - 256 : b);
  const hex2 = (b) => b.toString(16).toUpperCase().padStart(2, '0');
  const gearName = (g) => (g > 0 ? 'Ahead' : g < 0 ? 'Astern' : 'Neutral');
  const gearOf = (b) => Math.sign(int8(b)) * MAP.aheadSign;

  // actuator byte: C0 neutral, 4C shifting, 44 ahead engaged, 48 astern engaged, 40 at boot before the first C0
  function actState(b) {
    if ((b & 0x0C) === 0x0C) return 'shifting';
    if (b & 0x04) return 'ahead';
    if (b & 0x08) return 'astern';
    if (b & 0x80) return 'neutral';
    if (b === 0x40) return 'booting';
    return 'unknown';
  }

  /** Lever position in [-1, 1]: 0 neutral, +/-DETENT at the gear detent, +/-1 full throttle. */
  function leverPos(gear, thr) {
    const g = Math.sign(gear);
    const f = Math.max(0, Math.min(100, thr)) / 100;
    if (g === 0) return 0; // no gear demand: lever drawn at neutral
    return g * (DETENT + (1 - DETENT) * f);
  }

  // ---- parsing ----
  const FRAME_RE = /^\((\d+(?:\.\d+)?)\)\s+(\S+)\s+([0-9A-Fa-f]{1,8})#(R|[0-9A-Fa-f]*)\s*$/;
  const NOTE_RE = /^#\s*\((\d+(?:\.\d+)?)\)\s*(.*)$/;

  function parse(text) {
    const frames = [], notes = [], meta = {}, bad = [];
    const lines = String(text).split(/\r?\n/);
    for (let n = 0; n < lines.length; n++) {
      const line = lines[n].trim();
      if (!line) continue;
      let m = FRAME_RE.exec(line);
      if (m) {
        const idTxt = m[3];
        const rtr = m[4] === 'R';
        const data = [];
        if (!rtr) {
          if (m[4].length % 2) { bad.push(n + 1); continue; }
          for (let i = 0; i < m[4].length; i += 2) data.push(parseInt(m[4].substr(i, 2), 16));
        }
        frames.push({ t: +m[1], id: parseInt(idTxt, 16), ext: idTxt.length > 3, rtr, data, line: n + 1 });
        continue;
      }
      m = NOTE_RE.exec(line);
      if (m) {
        const text = m[2].trim();
        const lk = /^bitrate locked (\d+)/.exec(text);            // rev D firmware: rate confirmed by first frame
        if (lk) { meta.bitrate = +lk[1]; meta.lockedAt = +m[1]; }
        notes.push({ t: +m[1], text, line: n + 1 }); continue;
      }
      if (line[0] === '#') {
        const b = /bitrate\s+(\d+)/.exec(line); if (b) meta.bitrate = +b[1];
        const f = /file\s+(\S+)/.exec(line); if (f) meta.file = f[1];
        continue;
      }
      bad.push(n + 1);
    }
    // stable sort by time (the sniffer writes in order; this guards merged files)
    frames.forEach((f, i) => (f.i = i));
    frames.sort((a, b) => a.t - b.t || a.i - b.i);
    return { meta, frames, notes, badLines: bad };
  }

  // ---- model ----
  function build(text, opts) {
    opts = opts || {};
    const swap = !!opts.swap;
    const P = parse(text);
    const side = swap ? { A: 'stbd', B: 'port' } : { A: 'port', B: 'stbd' };
    const label = { port: 'Port', stbd: 'Starboard' };

    const model = {
      meta: P.meta, badLines: P.badLines, notes: P.notes, swap,
      frameCount: P.frames.length,
      t0: Math.min(P.frames.length ? P.frames[0].t : Infinity, P.notes.length ? P.notes[0].t : Infinity),
      t1: P.frames.length ? P.frames[P.frames.length - 1].t : 0,
      st: { 1: [], 2: [] },      // per station: {t, flags, port:{gear,thr,pos}, stbd:{...}, raw}
      lever: [],                 // = st[1], kept for v1 callers
      station2: [],              // {t, flags} of station 2, kept for v1 callers
      cmdLever: [],              // records of whichever station has command (station 1 when nobody does)
      act: { port: [], stbd: [] }, // {t, raw, state}
      hb: {},                    // node -> [{t, state}]
      buttons: [],               // {name, station, t0, t1, inferred}
      missed: [],                // {t0, t1, id, n}: periodic frames that never arrived
      busErr: [],                // {t, n, text}: firmware bus-error notes (rev D.3 and later)
      events: [],                // {t, kind, side, text}
      ids: {},                   // id -> {count, first, last, dlc}
    };
    model.lever = model.st[1];

    const ev = (t, kind, text, s) => model.events.push({ t, kind, side: s || null, text });
    const stnOf = {}; for (const k of Object.keys(MAP.stations)) stnOf[MAP.stations[k].id] = +k;
    const sName = (n) => MAP.stations[n].name;

    // tracking state for event derivation
    const prevFlags = { 1: null, 2: null };
    const lastSysChange = { [MAP.flagWarm]: -1e9, [MAP.flagSync]: -1e9 };
    const prevGear = { 1: { port: null, stbd: null }, 2: { port: null, stbd: null } };
    const lastGearChange = { port: null, stbd: null };
    const thrRun = { 1: { port: null, stbd: null }, 2: { port: null, stbd: null } };
    const prevAct = { port: null, stbd: null };
    const latest = { 1: null, 2: null };
    const lastT = { 1: null, 2: null };
    const lastSeen = {};
    const hasCmd = (n) => latest[n] && (latest[n].flags & MAP.flagCommand);

    for (const f of P.frames) {
      const id = f.id;
      const s = model.ids[id] || (model.ids[id] = { count: 0, first: f.t, last: f.t, dlc: f.data.length });
      s.count++; s.last = f.t;
      if (f.rtr || f.ext) continue;
      const per = PERIOD[id];
      if (per) {
        const pt = lastSeen[id];
        if (pt !== undefined) {
          const gap = f.t - pt, n = Math.round(gap / per) - 1;
          if (gap > 1.5 * per && gap < MISS_MAX_S && n >= 1) {
            model.missed.push({ t0: pt + per, t1: f.t, id, n });
            ev(pt + per, 'bus', `${n} frame${n > 1 ? 's' : ''} missing from ${ID_NAME[id]} (${gap.toFixed(3)} s gap).`);
          }
        }
        lastSeen[id] = f.t;
      }

      const sn = stnOf[id];
      if (sn && f.data.length >= 6) {
        const d = f.data, other = sn === 1 ? 2 : 1, who = sName(sn);
        const A = { gear: gearOf(d[1]), thr: d[2] };
        const B = { gear: gearOf(d[4]), thr: d[5] };
        A.pos = leverPos(A.gear, A.thr); B.pos = leverPos(B.gear, B.thr);
        const rec = { t: f.t, station: sn, flags: d[0], raw: d.map(hex2).join(' ') };
        rec[side.A] = A; rec[side.B] = B;
        model.st[sn].push(rec);
        if (sn === 2) model.station2.push({ t: f.t, flags: d[0] });
        latest[sn] = rec;
        // command-follower trace: the station in command, else station 1
        if ((d[0] & MAP.flagCommand) || (sn === 1 && !hasCmd(2))) model.cmdLever.push(rec);

        // flags / inferred buttons. A silence longer than HB_LOST_S is a power cycle: no buttons inferred across it.
        const gap = lastT[sn] === null ? null : f.t - lastT[sn];
        lastT[sn] = f.t;
        if (gap !== null && gap > HB_LOST_S) { prevFlags[sn] = null; }
        const pf = prevFlags[sn];
        if (pf === null) {
          ev(f.t, 'state', `${who} ${gap ? `back after ${gap.toFixed(1)} s silent` : 'first frame'}: command ${d[0] & MAP.flagCommand ? 'yes' : 'no'}, warm-up ${d[0] & MAP.flagWarm ? 'on' : 'off'}, sync ${d[0] & MAP.flagSync ? 'on' : 'off'} (0x${hex2(d[0])}).`);
        } else if (d[0] !== pf) {
          const ch = d[0] ^ pf;
          if (ch & MAP.flagCommand) {
            const on = !!(d[0] & MAP.flagCommand);
            if (on) {
              model.buttons.push({ name: 'command', station: sn, t0: f.t - BUTTON_HOLD_S, t1: f.t, inferred: true });
              ev(f.t, 'button', `${who}: takes command. Command LED on.`);
            } else ev(f.t, 'state', `${who} releases command. Command LED off.`);
          }
          for (const [bit, label] of [[MAP.flagWarm, 'Warm-up'], [MAP.flagSync, 'Synchronisation']]) {
            if (!(ch & bit)) continue;
            const on = !!(d[0] & bit);
            if (f.t - lastSysChange[bit] < 0.5) { lastSysChange[bit] = -1e9; continue; } // the other station mirroring it
            lastSysChange[bit] = f.t;
            if (bit === MAP.flagWarm) {
              model.buttons.push({ name: 'warm', station: sn, t0: f.t - BUTTON_HOLD_S, t1: f.t, inferred: true });
              ev(f.t, 'button', `${who}: Warm/Sync held 1.5 s. Warm-up ${on ? 'on, gear inhibited' : 'off, gear enabled'}.`);
            } else {
              model.buttons.push({ name: 'enginePort', station: sn, t0: f.t - BUTTON_HOLD_S, t1: f.t, inferred: true });
              model.buttons.push({ name: 'engineStbd', station: sn, t0: f.t - BUTTON_HOLD_S, t1: f.t, inferred: true });
              ev(f.t, 'button', `${who}: both Engine buttons held 1.5 s. Synchronisation ${on ? 'on, right lever drives both engines' : 'off'}.`);
            }
          }
          const other2 = ch & ~(MAP.flagCommand | MAP.flagWarm | MAP.flagSync | 0x40);
          if (other2) ev(f.t, 'state', `${who} flag byte 0x${hex2(pf)} → 0x${hex2(d[0])} (unmapped bits 0x${hex2(other2)}).`);
        }
        prevFlags[sn] = d[0];

        // gear demand + throttle runs
        for (const sd of ['port', 'stbd']) {
          const L = rec[sd], pg = prevGear[sn];
          if (pg[sd] !== null && L.gear !== pg[sd]) {
            ev(f.t, 'lever', `${who} ${label[sd].toLowerCase()} lever to ${gearName(L.gear).toLowerCase()}${d[0] & MAP.flagCommand ? '' : ' (not in command)'}.`, sd);
            if (d[0] & MAP.flagCommand) lastGearChange[sd] = { t: f.t, gear: L.gear };
          } else if (pg[sd] === null && (d[0] & MAP.flagCommand)) lastGearChange[sd] = { t: f.t, gear: L.gear };
          pg[sd] = L.gear;
          const run = thrRun[sn][sd];
          if (L.thr > 0 && !run) thrRun[sn][sd] = { t: f.t, peak: L.thr, gear: L.gear };
          else if (L.thr > 0 && run) run.peak = Math.max(run.peak, L.thr);
          else if (L.thr === 0 && run) {
            ev(run.t, 'throttle', `${who} ${label[sd].toLowerCase()} throttle opens, ${gearName(run.gear).toLowerCase()}. Peak ${run.peak} % before closing at ${f.t.toFixed(2)} s.`, sd);
            thrRun[sn][sd] = null;
          }
        }
        continue;
      }

      if ((id === MAP.actA || id === MAP.actB) && f.data.length >= 1) {
        const sd = id === MAP.actA ? side.A : side.B;
        const st = actState(f.data[0]);
        model.act[sd].push({ t: f.t, raw: f.data[0], state: st });
        if (prevAct[sd] !== null && st !== prevAct[sd]) {
          let txt = `${label[sd]} actuator ${st === 'shifting' ? 'shifting' : st === 'neutral' ? 'in neutral' : st === 'booting' ? 'booting' : 'engaged ' + st} (0x${hex2(f.data[0])})`;
          const lg = lastGearChange[sd];
          if (st !== 'shifting' && lg && f.t - lg.t < 5) txt += `, ${(f.t - lg.t).toFixed(2)} s after the lever`;
          ev(f.t, 'actuator', txt + '.', sd);
        }
        prevAct[sd] = st;
        continue;
      }

      if (id > 0x700 && id <= 0x77F && f.data.length >= 1) {
        const node = id - 0x700;
        const arr = model.hb[node] || (model.hb[node] = []);
        const st = f.data[0] & 0x7F;
        if (!arr.length) ev(f.t, 'node', `Node ${node} heartbeat, ${NMT[st] || '0x' + hex2(st)}.`);
        else {
          const prev = arr[arr.length - 1];
          if (f.t - prev.t > HB_LOST_S) {
            ev(prev.t + HB_LOST_S, 'node', `Node ${node} heartbeat lost.`);
            ev(f.t, 'node', `Node ${node} heartbeat back, ${NMT[st] || '0x' + hex2(st)}.`);
          } else if (prev.state !== st) ev(f.t, 'node', `Node ${node} now ${NMT[st] || '0x' + hex2(st)}.`);
        }
        arr.push({ t: f.t, state: st });
      }
    }
    // close open throttle runs at end of file
    for (const sn of [1, 2]) for (const sd of ['port', 'stbd']) {
      const run = thrRun[sn][sd];
      if (run) ev(run.t, 'throttle', `${sName(sn)} ${label[sd].toLowerCase()} throttle opens, ${gearName(run.gear).toLowerCase()}. Peak ${run.peak} %, still open at end of log.`, sd);
    }
    for (const [node, arr] of Object.entries(model.hb)) {
      const last = arr[arr.length - 1];
      if (model.t1 - last.t > HB_LOST_S) ev(last.t + HB_LOST_S, 'node', `Node ${node} heartbeat lost.`);
    }
    if (!isFinite(model.t0)) model.t0 = 0;
    for (const n of P.notes) {
      const be = /^bus errors?\b\D*(\d+)?/i.exec(n.text);
      if (be) { model.busErr.push({ t: n.t, n: be[1] ? +be[1] : 1, text: n.text }); ev(n.t, 'bus', `Sniffer: ${n.text}`); }
      else if (/rx queue overflow/i.test(n.text)) ev(n.t, 'bus', `Sniffer: ${n.text}`);
      else ev(n.t, 'note', `Note: ${n.text}`);
    }
    model.events.sort((a, b) => a.t - b.t);

    // startup backlog: at boot the sniffer queues frames while WiFi connects, then drains
    // them faster than the bus can carry them, so their timestamps are compressed.
    const fr = P.frames, W = 30;
    let i = 0, end = null;
    while (i + W < fr.length && fr[i + W].t - fr[i].t < W / 150) { end = fr[i + W].t; i++; }
    model.backlogEnd = end;
    return model;
  }

  // ---- queries ----
  function lastIdx(arr, t) {
    let lo = 0, hi = arr.length - 1, ans = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (arr[mid].t <= t) { ans = mid; lo = mid + 1; } else hi = mid - 1;
    }
    return ans;
  }

  /** Which station has command at time t (0 = nobody). */
  function commanderAt(model, t) {
    for (const n of [1, 2]) {
      const k = lastIdx(model.st[n], t);
      if (k >= 0 && (model.st[n][k].flags & MAP.flagCommand)) return n;
    }
    return 0;
  }

  /** Snapshot at time t for one head. station: 1, 2 or 'auto' (the station in command, else 1). */
  function stateAt(model, t, station) {
    const cmdr = commanderAt(model, t);
    const sn = station === 2 ? 2 : station === 1 ? 1 : (cmdr || 1);
    const other = sn === 1 ? 2 : 1;
    const out = { t, station: sn, commander: cmdr, port: null, stbd: null, flags: null, otherFlags: null, station2: null, raw: null, act: {}, hb: {}, buttons: {} };
    const arr = model.st[sn];
    const i = lastIdx(arr, t);
    if (i >= 0) {
      const a = arr[i], b = arr[i + 1];
      out.flags = a.flags;
      out.raw = a.raw;
      for (const sd of ['port', 'stbd']) {
        let pos = a[sd].pos;
        if (b && b.t - a.t > 0 && b.t - a.t < INTERP_MAX_S) {
          const k = Math.max(0, Math.min(1, (t - a.t) / (b.t - a.t)));
          pos = a[sd].pos + (b[sd].pos - a[sd].pos) * k;
        }
        out[sd] = { gear: a[sd].gear, thr: a[sd].thr, pos };
      }
    }
    const j = lastIdx(model.st[other], t);
    const o = j >= 0 ? model.st[other][j] : null;
    if (o) out.otherFlags = o.flags;
    const j2 = lastIdx(model.st[2], t);
    if (j2 >= 0) out.station2 = model.st[2][j2].flags;
    for (const sd of ['port', 'stbd']) {
      const k = lastIdx(model.act[sd], t);
      out.act[sd] = k >= 0 ? model.act[sd][k] : null;
    }
    for (const [node, harr] of Object.entries(model.hb)) {
      const k = lastIdx(harr, t);
      if (k < 0) { out.hb[node] = { seen: false }; continue; }
      const age = t - harr[k].t;
      out.hb[node] = { seen: true, alive: age <= HB_LOST_S, age, state: NMT[harr[k].state] || '0x' + hex2(harr[k].state) };
    }
    for (const b of model.buttons) if (b.station === sn && t >= b.t0 && t <= b.t1) out.buttons[b.name] = b;
    const f = out.flags;
    const cmd = f !== null && !!(f & MAP.flagCommand);
    const warm = f !== null && !!(f & MAP.flagWarm);
    const sync = f !== null && !!(f & MAP.flagSync);
    // Engine LEDs (reconstructed): steady when this head has command and that actuator is in neutral;
    const engLed = (sd) => (cmd && out.act[sd] && out.act[sd].state === 'neutral' ? 'on' : 'off');
    out.led = {
      command: cmd,
      warm: sync ? 'on' : warm ? 'blink' : 'off',
      enginePort: engLed('port'),
      engineStbd: engLed('stbd'),
    };
    return out;
  }

  return { MAP, HB_LOST_S, BUTTON_HOLD_S, DETENT, parse, build, stateAt, commanderAt, actState, leverPos, gearName };
});
