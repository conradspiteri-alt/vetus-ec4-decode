"""Shared candump log reader for the EC4 tools.

Log format (sniffer rev C and D):
    (1234.567890) can0 181#41FF1A0000FF1A00     frame
    # (1234.567890) free text note               timestamped note
    # anything else                              header comment

Only the Python standard library is used, so every tool runs on a bare python3.
"""
import re

FRAME_RE = re.compile(r'^\((\d+(?:\.\d+)?)\)\s+(\S+)\s+([0-9A-Fa-f]{1,8})#(R|[0-9A-Fa-f]*)\s*$')
NOTE_RE = re.compile(r'^#\s*\((\d+(?:\.\d+)?)\)\s*(.*)$')


class Frame(object):
    __slots__ = ('t', 'id', 'ext', 'rtr', 'data', 'line')

    def __init__(self, t, can_id, ext, rtr, data, line):
        self.t, self.id, self.ext, self.rtr, self.data, self.line = t, can_id, ext, rtr, data, line

    @property
    def hex(self):
        return ''.join('%02X' % b for b in self.data)


def read_log(path):
    """Return (frames, notes, bad_line_numbers). Frames are in file order."""
    frames, notes, bad = [], [], []
    with open(path, 'r', errors='replace') as fh:
        for n, raw in enumerate(fh, 1):
            line = raw.strip()
            if not line:
                continue
            m = FRAME_RE.match(line)
            if m:
                idtxt, payload = m.group(3), m.group(4)
                rtr = payload == 'R'
                if not rtr and len(payload) % 2:
                    bad.append(n)
                    continue
                data = b'' if rtr else bytes.fromhex(payload)
                frames.append(Frame(float(m.group(1)), int(idtxt, 16), len(idtxt) > 3, rtr, data, n))
                continue
            m = NOTE_RE.match(line)
            if m:
                notes.append((float(m.group(1)), m.group(2).strip(), n))
                continue
            if line.startswith('#'):
                continue
            bad.append(n)
    return frames, notes, bad


def backlog_end(frames, window=30):
    """Capture 1 (rev C) queued frames while WiFi connected and wrote them with compressed
    timestamps. Same rule as decode.js: a run where 30 frames span less than 30/150 s.
    Returns the time of the last compressed frame, or None."""
    end = None
    i = 0
    while i + window < len(frames) and frames[i + window].t - frames[i].t < window / 150.0:
        end = frames[i + window].t
        i += 1
    return end
