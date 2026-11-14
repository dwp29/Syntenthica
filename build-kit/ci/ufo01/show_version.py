#!/usr/bin/env python3
"""Print the version baked into a built Image.gz, or say plainly that it is absent."""
import gzip
import re
import sys

raw = gzip.open(sys.argv[1], "rb").read()
m = re.search(rb"Linux version ([0-9][^\x00 ]+)", raw)
print("versi tertanam:", m.group(1).decode() if m else "TIDAK DITEMUKAN")
