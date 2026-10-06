#!/usr/bin/env python3
"""Inline decode.js and the sample log into app.html.
Outputs:
  dist/lever-playback.body.html  - Artifact publish (no doctype/head/body, the host adds them)
  dist/EC4-Lever-Playback.html   - standalone file for offline use on the boat laptop
"""
import os, pathlib
here = pathlib.Path(__file__).parent
app = (here / 'app.html').read_text()
dec = (here / 'decode.js').read_text()
log = (here / '..' / '..' / 'captures' / 'sample' / 'ec4-sample.log').read_text()   # capture 3 excerpt, default sample
log1 = (here / '..' / '..' / 'captures' / 'capture1.log').read_text()  # capture 1
for L in (log, log1): assert '</script' not in L.lower()
body = app.replace('/*__DECODE__*/', dec).replace('/*__SAMPLE__*/', log).replace('/*__SAMPLE1__*/', log1)
os.makedirs(here / 'dist', exist_ok=True)
(here / 'dist' / 'lever-playback.body.html').write_text(body)
standalone = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
              '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
              '<style>body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n'
              '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
(here / 'dist' / 'EC4-Lever-Playback.html').write_text(standalone)
print('ok', len(body), len(standalone))
