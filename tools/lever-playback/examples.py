#!/usr/bin/env python3
"""Simple ahead and astern examples for each helm, as annotated viewer screenshots.

Builds docs/images/examples/*.png from real capture frames. Each example is a moment where one
helm holds command, the other helm's levers are in neutral, and the actuators report the gear
the levers ask for. Needs Playwright with Chromium. Run build.py first.
"""
import asyncio, os, re
from playwright.async_api import async_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..'))
HTML = 'file://' + os.path.join(HERE, 'dist', 'EC4-Lever-Playback.html')
OUT = os.path.join(REPO, 'docs', 'images', 'examples')
CAP = lambda n: os.path.join(REPO, 'captures', n)

GEAR = {0xFF: 'AHEAD', 0x00: 'NEUTRAL', 0x01: 'ASTERN'}
ACT = {0xC0: 'neutral', 0x44: 'engaged AHEAD', 0x48: 'engaged ASTERN', 0x4C: 'shifting', 0x40: 'booting'}
NAME = {'181': 'Main helm', '282': 'Flybridge'}
DISPLAY = {'capture1.log': 'capture 1 (23 Sep 2026)', 'capture2.log': 'capture 2 (27 Sep 2026, not published)'}

# (file, log time, output name, helm id): moments at idle with the gear engaged
EXAMPLES = [
    ('capture2.log', 1282.4, '01-main-helm-ahead', '181'),
    ('capture1.log', 82.2, '02-main-helm-astern-port', '181'),
    ('capture1.log', 95.0, '03-main-helm-astern-starboard', '181'),
    ('capture2.log', 583.4, '04-flybridge-ahead-port', '282'),
    ('capture2.log', 593.2, '05-flybridge-ahead-starboard', '282'),
]


def state_at(fn, t):
    """Latest frame of each ID at log time t, read from the capture itself."""
    last = {}
    for line in open(CAP(fn)):
        m = re.match(r'\((\S+)\) can0 (181|282|384|485)#(\S+)', line)
        if not m:
            continue
        if float(m.group(1)) > t:
            break
        last[m.group(2)] = bytes.fromhex(m.group(3))
    return last


def describe(fn, t, helm):
    st = state_at(fn, t)
    a, other = st[helm], st['282' if helm == '181' else '181']
    assert a[0] & 1 and not any(other[1:]), 'example must have one helm in command, other levers neutral'
    levers = []
    for side, g, th in (('port', 1, 2), ('starboard', 4, 5)):
        levers.append('%s %s%s' % (side, GEAR[a[g]], '' if a[g] == 0 else ' at %d %% throttle' % a[th]))
    sides = [(side, GEAR[a[g]]) for side, g in (('port', 1), ('starboard', 4)) if a[g] != 0]
    if len(sides) == 2 and sides[0][1] == sides[1][1]:
        title = '%s in command: both levers %s' % (NAME[helm], sides[0][1])
    else:
        title = '%s in command: %s' % (NAME[helm], ', '.join('%s lever %s' % x for x in sides))
    detail = ('Levers sent by the %s: %s. Gearboxes report: port %s, starboard %s. '
              'The %s is not in command, so its levers are ignored (here they are in neutral).') % (
        NAME[helm].lower(), ', '.join(levers), ACT[st['384'][0]], ACT[st['485'][0]],
        NAME['282' if helm == '181' else '181'].lower())
    raw = 'Source: %s at %.1f s, engines off. Raw: 0x%s#%s, 0x384#%02X, 0x485#%02X' % (
        DISPLAY.get(fn, fn), t, helm, a.hex().upper(), st['384'][0], st['485'][0])
    return title, detail, raw


BANNER_JS = """([title, detail, src]) => {
  let b = document.getElementById('ex-banner');
  if (!b) {
    b = document.createElement('div'); b.id = 'ex-banner';
    b.style.cssText = 'margin:0 0 12px;padding:14px 18px;border-radius:12px;background:#12324a;color:#fff;font:15px/1.4 system-ui,sans-serif';
    const grid = document.getElementById('card1').parentElement;
    grid.parentElement.insertBefore(b, grid);
  }
  b.innerHTML = '<div style="font-size:22px;font-weight:700;margin-bottom:4px">' + title + '</div>' +
                '<div>' + detail + '</div><div style="opacity:.7;margin-top:4px;font-size:13px">' + src + '</div>';
}"""

LEGEND_JS = """() => {
  const panel = document.querySelector('.panel.sys');
  if (document.getElementById('ex-legend')) return;
  for (const c of panel.children) c.style.display = 'none';
  const lg = document.createElement('div'); lg.id = 'ex-legend'; panel.appendChild(lg);
  lg.innerHTML = '<div style="font:600 13px/1.2 system-ui,sans-serif;letter-spacing:.08em;margin-bottom:8px">HOW TO READ THIS</div>' +
    '<div style="font:14px/1.5 system-ui,sans-serif">' +
    '<b>Red border, red COMMAND light:</b> this helm has command. The gearboxes follow its levers.<br>' +
    '<b>Dimmed helm:</b> not in command. Its levers are ignored.<br>' +
    '<b>Green ENGINE light:</b> that engine is in neutral (drawn by the viewer, not sent on the bus).<br>' +
    '<b>Actuator:</b> what the gearbox reports back (44 ahead, 48 astern, C0 neutral).</div>';
}"""

UNION_JS = """() => {
  const ids = ['ex-banner', 'card1', 'card2', 'eng-port', 'eng-stbd'];
  const r = ids.map(i => document.getElementById(i).getBoundingClientRect()).concat([document.querySelector('.panel.sys').getBoundingClientRect()]);
  const x0 = Math.min(...r.map(a => a.left)), y0 = Math.min(...r.map(a => a.top));
  const x1 = Math.max(...r.map(a => a.right)), y1 = Math.max(...r.map(a => a.bottom));
  return {x: x0 - 8, y: y0 - 8 + window.scrollY, width: x1 - x0 + 16, height: y1 - y0 + 16};
}"""


async def main():
    os.makedirs(OUT, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch()
        pg = await b.new_page(viewport={'width': 1400, 'height': 1400}, color_scheme='light')
        await pg.goto(HTML)
        await pg.wait_for_timeout(1200)
        loaded = None
        for fn, t, name, helm in EXAMPLES:
            if not os.path.exists(CAP(fn)):
                print('skip', name, '(', fn, 'not in captures/ )')
                continue
            title, detail, raw = describe(fn, t, helm)
            if loaded != fn:
                await pg.set_input_files('#file', CAP(fn))
                await pg.wait_for_timeout(1500)
                loaded = fn
            await pg.evaluate("t=>{const s=document.getElementById('scrub'); s.value=t; s.dispatchEvent(new Event('input',{bubbles:true}));}", t)
            await pg.wait_for_timeout(300)
            await pg.evaluate(BANNER_JS, [title, detail, raw])
            await pg.evaluate(LEGEND_JS)
            await pg.wait_for_timeout(200)
            clip = await pg.evaluate(UNION_JS)
            await pg.screenshot(path=os.path.join(OUT, name + '.png'), clip=clip)
            print(name, '|', title)
        await b.close()

asyncio.run(main())
