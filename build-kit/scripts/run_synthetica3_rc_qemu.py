#!/usr/bin/env python3
"""Run each synthetic ARM installer test in a bounded, isolated process group.

The writer case only uses the test's newly created loop-backed synthetic image;
no physical device is used. Passing does not verify a real Android recovery.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = 'test_synthetica2_installer_qemu.SyntheticRepackTests.'
REPACK = (
    'test_corrupted_repacked_header_and_vbmeta_are_rejected',
    'test_detected_magisk_ramdisk_is_rejected',
    'test_missing_footer_or_wrong_header_is_rejected_before_output',
    'test_repack_preserves_sections_header_and_vbmeta_bytes',
    'test_wrong_kernel_or_reference_dtb_is_rejected',
)
WRITER = ('test_loop_backed_writer_round_trip',)
REQUIRED_ENV = ('S2_IMAGE', 'S2_ARM_BB', 'S2_ARM_MAGISKBOOT', 'S2_AVBTOOL', 'S2_ANYKERNEL')


def run_case(name: str, seconds: int) -> None:
    command = [sys.executable, '-u', '-m', 'unittest', BASE + name, '-v']
    proc = subprocess.Popen(command, cwd=ROOT / 'tests', stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        output, _ = proc.communicate(timeout=seconds)
    except subprocess.TimeoutExpired:
        # The process has its own session; never signal the calling shell/job.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        output, _ = proc.communicate(timeout=10)
        print(output, flush=True)
        raise ValueError(f'{name} timed out after {seconds} seconds')
    print(output, flush=True)
    if proc.returncode != 0:
        raise ValueError(f'{name} failed with status {proc.returncode}')
    if 'skipped' in output.lower() or '\nOK\n' not in output:
        raise ValueError(f'{name} did not run to a successful non-skipped result')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('repack', 'writer'), required=True)
    parser.add_argument('--timeout', type=int, default=75)
    args = parser.parse_args()
    if not 5 <= args.timeout <= 600:
        raise ValueError('timeout must be 5-600 seconds per test')
    if os.environ.get('S2_QEMU_INTEGRATION') != '1':
        raise ValueError('S2_QEMU_INTEGRATION=1 is required')
    for key in REQUIRED_ENV:
        value = os.environ.get(key)
        if not value or not Path(value).is_file():
            raise ValueError(f'missing test input: {key}')
    if args.suite == 'writer':
        if os.geteuid() != 0 or os.environ.get('S2_LOOP_WRITER') != '1':
            raise ValueError('writer requires root and S2_LOOP_WRITER=1')
        cases = WRITER
    else:
        cases = REPACK
    for name in cases:
        run_case(name, args.timeout)
    print(f'{args.suite}: {len(cases)} synthetic test(s) passed; no physical device was tested.')


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f'Synthetic installer test refused: {exc}', file=sys.stderr)
        sys.exit(1)
