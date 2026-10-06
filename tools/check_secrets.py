#!/usr/bin/env python3
"""Fail if firmware/sniffer/ec4_can_sniffer/secrets.h holds anything but the placeholders.

Run before every commit:  python3 tools/check_secrets.py   (exit 0 = safe to commit)
"""
import os
import re
import sys

P = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'firmware', 'sniffer', 'ec4_can_sniffer', 'secrets.h')
s = open(P, encoding='utf-8').read()
pairs = re.findall(r'\{\s*"([^"]*)"\s*,\s*"([^"]*)"\s*\}', s)
bad = [x for pair in pairs for x in pair if not x.startswith('CHANGE_ME')]
if not pairs or bad:
    print('secrets.h contains real-looking values: do not commit it.')
    print('Restore the CHANGE_ME placeholders, or run: git update-index --skip-worktree firmware/sniffer/ec4_can_sniffer/secrets.h')
    sys.exit(1)
print('secrets.h: placeholders only, safe to commit.')
