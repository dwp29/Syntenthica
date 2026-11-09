#!/usr/bin/env python3
"""Read-only ADB log capture for recovery; does not install, flash or reboot."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

MAX_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 128
NAME = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$')
INSTALL_NAME = re.compile(r'^install-log-[A-Za-z0-9_.-]{1,110}\.txt$')
INSTALL_DIRS = ('/sdcard/Synthetica', '/data/media/0/Synthetica',
                '/storage/emulated/0/Synthetica', '/cache/Synthetica',
                '/cache/recovery/Synthetica')
MAX_INSTALL_LOGS = 20
TIMEOUT = 30


def timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def run_adb(adb: str, serial: str | None, args: list[str]) -> tuple[int | None, bytes, str]:
    command = [adb] + (['-s', serial] if serial else []) + args
    try:
        # Bound memory consumption even if a recovery returns an unexpectedly
        # large log. The temporary file is local and removed on close.
        with tempfile.TemporaryFile() as output:
            result = subprocess.run(command, stdout=output, stderr=subprocess.DEVNULL,
                                    timeout=TIMEOUT, check=False)
            output.seek(0)
            data = output.read(MAX_BYTES + 1)
        # Do not store raw stderr: it may contain device identifiers or paths.
        return result.returncode, data, 'ok' if result.returncode == 0 else 'command_failed'
    except subprocess.TimeoutExpired:
        return None, b'', 'timeout'
    except OSError:
        return None, b'', 'adb_unavailable'


def store(out: Path, name: str, data: bytes) -> dict:
    truncated = len(data) > MAX_BYTES
    data = data[:MAX_BYTES]
    path = out / name
    with path.open('xb') as file:
        file.write(data)
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {'status': 'truncated' if truncated else ('captured' if data else 'empty'),
            'saved_as': name, 'bytes_saved': len(data),
            'sha256_saved': hashlib.sha256(data).hexdigest()}


def capture_file(out: Path, adb: str, serial: str | None, remote: str, name: str) -> dict:
    code, data, status = run_adb(adb, serial, ['exec-out', 'cat', remote])
    if code != 0:
        return {'status': status, 'exit_code': code}
    return store(out, name, data)


def capture(stage: str, out: Path, adb: str, serial: str | None) -> dict:
    if stage not in ('install', 'boot'):
        raise ValueError('Invalid capture stage')
    if out.exists() or out.is_symlink():
        raise ValueError('Output directory must not exist; choose a new path')
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    try:
        out.chmod(0o700)
    except OSError:
        pass
    report = {'scope': 'LOCAL_READ_ONLY_ADB_CAPTURE_NOT_A_BOOT_FIX',
              'stage': stage, 'started_utc': timestamp(), 'max_bytes_per_file': MAX_BYTES,
              'notes': ['No flash, reboot, mounts, properties or device files are changed.',
                        'Logs may contain sensitive data. Review before sharing.',
                        'A recovery log is not automatically the failed Android kernel log.',
                        'Empty, absent or inaccessible logs do not prove no crash.'],
              'files': {}}
    code, state, status = run_adb(adb, serial, ['get-state'])
    valid_states = {b'device': 'device', b'recovery': 'recovery'}
    report['adb_state'] = valid_states.get(state.strip(), 'unexpected_state') if code == 0 else status
    files = report['files']
    if report['adb_state'] in ('device', 'recovery'):
        if stage == 'boot':
            # Capture persistent records first: later recovery activity can overwrite them.
            code, listing, state = run_adb(adb, serial, ['shell', 'ls', '-1', '/sys/fs/pstore'])
            report['pstore_listing_status'] = state
            if code == 0:
                if len(listing) > MAX_BYTES:
                    report['pstore_listing_status'] = 'truncated'
                    listing = listing[:MAX_BYTES].rsplit(b'\n', 1)[0]
                names = []
                skipped = 0
                for raw in listing.splitlines():
                    try:
                        name = raw.decode('ascii').rstrip('\r')
                    except UnicodeDecodeError:
                        skipped += 1
                        continue
                    if not NAME.fullmatch(name) or name in ('.', '..') or name in names:
                        skipped += 1
                        continue
                    names.append(name)
                report['pstore_skipped_or_duplicate_names'] = skipped
                report['pstore_count_over_limit'] = max(0, len(names) - MAX_ENTRIES)
                for name in names[:MAX_ENTRIES]:
                    files['pstore/' + name] = capture_file(out, adb, serial,
                        '/sys/fs/pstore/' + name, 'pstore-' + name)
            files['last_kmsg'] = capture_file(out, adb, serial, '/proc/last_kmsg', 'last-kmsg.bin')
        files['recovery_log'] = capture_file(out, adb, serial, '/tmp/recovery.log', 'recovery.log')
        # The installer can put its own timestamped log in one of these known
        # locations. They can be aliases or contain older unrelated sessions.
        report['installer_listing_status'] = {}
        total = 0
        for index, directory in enumerate(INSTALL_DIRS):
            code, listing, state = run_adb(adb, serial, ['shell', 'ls', '-1', directory])
            if code == 0 and len(listing) > MAX_BYTES:
                state = 'truncated'
                listing = listing[:MAX_BYTES].rsplit(b'\n', 1)[0]
            report['installer_listing_status'][directory] = state
            if code != 0:
                continue
            for raw in listing.splitlines():
                try:
                    name = raw.decode('ascii').rstrip('\r')
                except UnicodeDecodeError:
                    continue
                if not INSTALL_NAME.fullmatch(name):
                    continue
                if total >= MAX_INSTALL_LOGS:
                    report['installer_log_limit_reached'] = True
                    break
                key = directory + '/' + name
                if key in files:
                    continue
                files[key] = capture_file(out, adb, serial, key, f'installer-{index}-{name}')
                total += 1
    report['completed_utc'] = timestamp()
    report_path = out / 'STATUS.json'
    with report_path.open('x', encoding='utf-8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write('\n')
    try:
        report_path.chmod(0o600)
    except OSError:
        pass
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('install', 'boot'), required=True)
    parser.add_argument('--out', type=Path, required=True, help='new local output directory; never overwritten')
    parser.add_argument('--adb', default='adb', help='path to adb executable, default: adb on PATH')
    parser.add_argument('--serial', help='optional ADB selector if multiple devices are connected; not saved')
    args = parser.parse_args()
    if hasattr(os, 'umask'):
        os.umask(0o077)
    report = capture(args.stage, args.out, args.adb, args.serial)
    print(f"Saved local report to {args.out} (ADB: {report['adb_state']}).")
    for name, item in report['files'].items():
        print(f"{name}: {item['status']}")
    print('Review STATUS.json and sensitive logs privately; do not upload raw logs publicly.')
    return 0 if report['adb_state'] in ('device', 'recovery') else 2


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        raise SystemExit(2)
