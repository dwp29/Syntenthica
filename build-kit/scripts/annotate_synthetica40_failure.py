#!/usr/bin/env python3
"""Expose concise CI diagnostics as check annotations, without private files."""
import re
import sys
from pathlib import Path

if len(sys.argv) != 3:
    raise SystemExit("usage: annotate_synthetica40_failure.py TITLE LOG")

title, path = sys.argv[1], Path(sys.argv[2])
rows = path.read_text(errors='replace').splitlines() if path.is_file() else ['No diagnostic log was written']
indexes = [i for i, row in enumerate(rows) if re.search(
    r'error:|fatal error|undefined reference|^ERROR:|Traceback|^FAILED|AssertionError|Unresolved configuration', row, re.I)]
chosen = []
for index in indexes[-10:]:
    chosen.extend(rows[max(0, index - 2):min(len(rows), index + 4)])
if not chosen:
    chosen = rows[-35:]
# All content originates in public build logs. Bound the annotation size and
# encode GitHub command delimiters rather than letting a log forge commands.
text = '\n'.join(dict.fromkeys(chosen))[-10000:]
for start in range(0, len(text), 1800):
    part = text[start:start+1800].replace('%', '%25').replace('\r', '%0D').replace('\n', '%0A')
    print(f'::error title={title} {start//1800+1}::{part}')
