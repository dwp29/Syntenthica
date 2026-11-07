#!/usr/bin/env python3
"""Run the exact collector shell on an Android emulator with FAKE filesystem data.

No recovery ZIP or kernel is installed and no actual block device is read. Only
files under a newly created /data/local/tmp fixture are used. Not a TWRP or
physical-device test.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import re
import struct
import subprocess
import tempfile
import zipfile

REMOTE = '/data/local/tmp/synthetica-collector-fixture-ci'


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--zip', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'emulator-\d+', args.serial):
        raise ValueError('refusing anything other than an emulator serial')

    def adb(*cmd: str, check: bool = True) -> str:
        result = subprocess.run(['adb', '-s', args.serial, *cmd], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if check and result.returncode:
            raise RuntimeError(f'adb {cmd!r} failed ({result.returncode}): {result.stderr} {result.stdout}')
        return result.stdout.replace('\r\n', '\n')

    if adb('shell', 'getprop', 'ro.kernel.qemu').strip() != '1':
        raise ValueError('Android is not reporting an emulator')
    if 'collectorci' not in adb('emu', 'avd', 'name'):
        raise ValueError('Emulator console did not confirm the expected CI AVD')
    exists = subprocess.run(['adb', '-s', args.serial, 'shell', 'test', '-e', REMOTE])
    if exists.returncode == 0:
        raise ValueError('Refusing to overwrite an existing emulator fixture')

    args.output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='collector-android-ci-') as temp:
        local = Path(temp) / 'fixture'
        def put(path: str, contents: str | bytes) -> Path:
            dst = local / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(contents.encode() if isinstance(contents, str) else contents)
            return dst
        put('.synthetica-collector-fixture', '')
        put('proc/mounts', f'/dev/fake {REMOTE}/data ext4 rw 0 0\n'
            f'/dev/fake {REMOTE}/system ext4 ro 0 0\n'
            f'tmpfs {REMOTE}/tmp tmpfs rw 0 0\n')
        put('proc/cmdline', 'androidboot.slot_suffix=_a androidboot.serialno=SERIAL-PRIVATE\n')
        put('tmp/recovery.log', 'Synthetic kernel installation\nPREPARE FAILED: DTB mismatch\nError 1\n')
        put('proc/last_kmsg', 'synthetic previous panic\n')
        put('sys/fs/pstore/dmesg-ramoops-0', 'synthetic pstore panic\n')
        put('system/build.prop', 'ro.build.version.release=15\nro.serialno=SERIAL-PRIVATE\n')
        put('data/media/0/.placeholder', '')
        put('bin/getprop', '''#!/system/bin/sh
case "$1" in
ro.product.device) echo fake-device;;
ro.build.version.release) echo 14;;
ro.boot.slot_suffix) echo _a;;
esac
''')
        put('bin/dmesg', '#!/system/bin/sh\necho synthetic-recovery-dmesg\n')
        put('bin/logcat', '#!/system/bin/sh\necho synthetic-recovery-logcat\n')
        for name in ('mount', 'umount', 'reboot', 'setprop', 'su', 'fastboot', 'flash_image'):
            put('bin/' + name, '#!/system/bin/sh\necho called >> "$SYNT_COLLECTOR_TEST_ROOT/unsafe-called"\nexit 87\n')
        data = bytearray(4096)
        data[:8] = b'ANDROID!'
        for offset, number in ((8, 123456), (12, 0x10008000), (16, 65432),
                               (36, 4096), (40, 2), (1644, 1660)):
            struct.pack_into('<I', data, offset, number)
        data[500:520] = b'DO_NOT_COPY_SERIAL!!'
        put('dev/block/bootdevice/by-name/boot_a', bytes(data))
        with zipfile.ZipFile(args.zip) as z:
            script = z.read('collector.sh')
            if script != z.read('META-INF/com/google/android/update-binary'):
                raise AssertionError('ZIP and adb shell payloads differ')
            put('collector.sh', script)
        # Push the fake tree only after the checks above. No real /proc, /sys or
        # block paths are read because every input is under the fixture root.
        adb('push', str(local), REMOTE)
        adb('shell', 'chmod', '755', *(REMOTE + '/bin/' + n for n in
            ('getprop', 'dmesg', 'logcat', 'mount', 'umount', 'reboot', 'setprop', 'su', 'fastboot', 'flash_image')))
        adb('shell', 'ln', '-s', REMOTE + '/data/media/0', REMOTE + '/sdcard')

        def run_collector(name: str) -> str:
            command = f'SYNT_COLLECTOR_TEST_ROOT={REMOTE} sh {REMOTE}/collector.sh'
            output = adb('shell', command)
            (args.output / f'{name}.txt').write_text(output)
            if 'Report folder: ' not in output:
                raise AssertionError('no report in Android output: ' + output)
            return output

        first = run_collector('mounted')
        m = re.search(r'^Report folder: (.+)$', first, re.MULTILINE)
        assert m
        report = m.group(1).strip()
        if not report.startswith(REMOTE + '/sdcard/Synthetica-logs/'):
            raise AssertionError('unexpected mounted destination: ' + report)
        def read(name: str) -> str:
            return adb('shell', 'cat', report + '/' + name)
        status = read('STATUS.tsv')
        for token in ('01-recovery-current.log\tOK', 'pstore-dmesg-ramoops-0.log\tOK',
                      '10-dmesg-recovery.log\tOK', '11-logcat-recovery.log\tOK',
                      '13-mounted-rom-properties.txt\tOK', 'report\tCOMPLETE'):
            if token not in status:
                raise AssertionError(f'missing {token!r} in Android status:\n{status}')
        if 'PREPARE FAILED: DTB mismatch' not in read('15-error-lines.txt'):
            raise AssertionError('recovery error was not captured')
        context = read('12-recovery-context.txt')
        if 'ro.boot.slot_suffix=_a' not in context or 'SERIAL-PRIVATE' in context:
            raise AssertionError('allowlisted context incorrect')
        rom = read('13-mounted-rom-properties.txt')
        if 'ro.build.version.release=15' not in rom or 'SERIAL-PRIVATE' in rom:
            raise AssertionError('mounted ROM properties incorrect')
        layout = read('14-partition-layout.txt')
        if ('header_version=2 kernel_bytes=123456 ramdisk_bytes=65432' not in layout
                or 'legacy_header_bytes=1660' not in layout):
            raise AssertionError('Android shell could not decode synthetic boot header: ' + layout)
        if 'DO_NOT_COPY_SERIAL' in layout:
            raise AssertionError('raw boot header leaked')
        if subprocess.run(['adb', '-s', args.serial, 'shell', 'test', '-e', REMOTE + '/unsafe-called']).returncode == 0:
            raise AssertionError('a prohibited mutating command was executed')
        # Pull the physical fixture path rather than the /sdcard symlink; some
        # adbd sync implementations reject traversing a symbolic link.
        physical_report = report.replace(REMOTE + '/sdcard/', REMOTE + '/data/media/0/', 1)
        adb('pull', physical_report, str(args.output / 'report'))
        (args.output / 'status-android.txt').write_text(status)

        # A writable directory without a persistent mount must be flagged as
        # temporary; no real mount is attempted.
        put('proc/mounts', f'tmpfs {REMOTE}/tmp tmpfs rw 0 0\n')
        adb('push', str(local / 'proc/mounts'), REMOTE + '/proc/mounts')
        second = run_collector('volatile')
        if 'TEMPORARY /tmp' not in second or f'Report folder: {REMOTE}/tmp/Synthetica-logs/' not in second:
            raise AssertionError('unmounted fallback was not labeled volatile: ' + second)
        adb('pull', REMOTE + '/tmp/Synthetica-logs', str(args.output / 'volatile-report'))
        if subprocess.run(['adb', '-s', args.serial, 'shell', 'test', '-e', REMOTE + '/unsafe-called']).returncode == 0:
            raise AssertionError('a prohibited mutating command was executed')
    print('Android emulator shell tests passed on fake data; no actual recovery/kernel/device was tested.', flush=True)


if __name__ == '__main__':
    main()
