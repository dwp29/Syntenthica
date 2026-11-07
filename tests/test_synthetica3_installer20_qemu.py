"""Run the 2.0 AnyKernel core on synthetic regular files under QEMU only.

Opt in with S3_INSTALLER20_QEMU=1 and S3_INSTALLER20_ZIP=<built ZIP>.
This harness redirects device/data/log paths in temporary *copies* of the entry
script, mocks mount/chown/blockdev, and bounds dd to one regular fixture. It
never runs update-binary or touches an actual recovery/partition/device.
"""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('bootfixture20', ROOT / 'tests/test_synthetica3_boot.py')
fixture = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fixture)

IMAGE_SHA = '92316b2d52af2a29ec2a5da48cbc18b9b33cebc5727ecb1b3c21ef27b9029deb'
KSUD_SHA = '52ba3da465459bfbac98dd25c53f8d31f93ee5a8ee89d84f67a28fe0d18cdef2'


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def replace_once(text: str, old: str, new: str) -> str:
    if text.count(old) != 1:
        raise AssertionError(f'fixture rewrite requires exactly one occurrence: {old!r}')
    return text.replace(old, new, 1)


@unittest.skipUnless(os.environ.get('S3_INSTALLER20_QEMU') == '1', 'synthetic ARM integration is opt-in')
class OriginalAnyKernelTests(unittest.TestCase):
    def setUp(self):
        for command in ('qemu-arm-static', 'busybox', 'python3'):
            self.assertIsNotNone(shutil.which(command), command)
        self.temp = tempfile.TemporaryDirectory(prefix='s320-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.home = self.root / 'home'
        self.tools = self.home / 'tools'
        self.bin = self.root / 'bin'
        self.arm = self.root / 'arm'
        self.fs = self.root / 'fs'
        self.boot = self.root / 'boot'
        for directory in (self.home, self.tools, self.bin, self.arm, self.fs):
            directory.mkdir(parents=True, exist_ok=True)
        zip_path = Path(os.environ['S3_INSTALLER20_ZIP']).resolve()
        with zipfile.ZipFile(zip_path) as z:
            self.assertIsNone(z.testzip())
            entry = z.read('anykernel.sh').decode('utf-8')
            core = z.read('tools/ak3-core.sh').decode('utf-8')
            for name in ('Image.gz', 'ksud'):
                (self.home / name).write_bytes(z.read(name))
            for name in ('busybox', 'magiskboot'):
                (self.arm / name).write_bytes(z.read('tools/' + name))
                (self.arm / name).chmod(0o755)
        self.assertEqual(sha((self.home / 'Image.gz').read_bytes()), IMAGE_SHA)
        self.assertEqual(sha((self.home / 'ksud').read_bytes()), KSUD_SHA)
        # These substitutions only occur in scratch copies used by this test.
        entry = replace_once(entry, 'BLOCK=/dev/block/bootdevice/by-name/boot;',
                             f'BLOCK={shlex.quote(str(self.boot))};')
        for source, dest in (
                ('/dev/block/bootdevice/by-name/userdata', self.fs / 'dev/block/bootdevice/by-name/userdata'),
                ('/dev/block/by-name/userdata', self.fs / 'dev/block/by-name/userdata'),
                ('/storage/emulated/0', self.fs / 'storage/emulated/0'),
                ('/sdcard', self.fs / 'sdcard'),
                ('/data', self.fs / 'data'),
                ('/cache', self.fs / 'cache')):
            entry = entry.replace(source, str(dest))
        core = core.replace('/dev/block', str(self.fs / 'dev/block'))
        core = replace_once(core, '    /dev/*)\n      if [ "$SLOT" ]',
                            f'    /dev/*|{shlex.quote(str(self.root))}/*)\n      if [ "$SLOT" ]')
        (self.home / 'anykernel.sh').write_text(entry)
        (self.tools / 'ak3-core.sh').write_text(core)
        for name in ('busybox', 'magiskboot'):
            wrapper = self.tools / name if name == 'busybox' else self.bin / name
            wrapper.write_text('#!/bin/sh\nexec qemu-arm-static ' + shlex.quote(str(self.arm / name)) + ' "$@"\n')
            wrapper.chmod(0o755)
        (self.bin / 'cpio').symlink_to(shutil.which('busybox'))
        for command, result in (('mount', 1), ('chown', 0), ('chcon', 0), ('blockdev', 0)):
            path = self.bin / command
            path.write_text(f'#!/bin/sh\nexit {result}\n')
            path.chmod(0o755)
        # The original script clears a finite *block device* with dd from zero.
        # Here the target is a regular file, so bound that operation and reject
        # every output outside this temporary directory. No /dev write is possible.
        dd = self.bin / 'dd'
        dd.write_text('''#!/usr/bin/env python3
import os, pathlib, stat, sys
args = sys.argv[1:]
parts = dict(arg.split('=', 1) for arg in args if '=' in arg)
root = pathlib.Path(os.environ['FIXTURE_ROOT']).resolve()
boot = pathlib.Path(os.environ['FIXTURE_BOOT']).resolve()
out = parts.get('of')
if out:
    path = pathlib.Path(out).resolve()
    if not path.is_relative_to(root) or (path.exists() and not stat.S_ISREG(path.stat().st_mode)):
        raise SystemExit('dd output is not a regular fixture file')
    if path == boot:
        if parts.get('if') == '/dev/zero':
            size = boot.stat().st_size
            with boot.open('r+b') as f:
                chunk = bytes(1048576)
                for _ in range(size // len(chunk)):
                    f.write(chunk)
                f.write(bytes(size % len(chunk)))
        else:
            src = pathlib.Path(parts['if']).resolve()
            if not src.is_relative_to(root) or not src.is_file():
                raise SystemExit('dd input is not a regular fixture file')
            with src.open('rb') as r, boot.open('r+b') as w:
                w.seek(0)
                while chunk := r.read(1048576):
                    w.write(chunk)
        raise SystemExit(0)
os.execv('/usr/bin/dd', ['dd', *args])
''')
        dd.chmod(0o755)

    def make_boot(self, tree: bytes):
        rd = self.root / 'ramdisk-fixture'
        rd.mkdir()
        (rd / 'init').write_bytes(b'#!/bin/sh\nexit 0\n')
        cpio = subprocess.run(['busybox', 'cpio', '-o', '-H', 'newc'], cwd=rd,
                              input=b'init\n', stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout
        image = fixture.boot(kernel=b'old-synthetic-kernel', ramdisk=gzip.compress(cpio, mtime=0), tree=tree)
        self.boot.write_bytes(image + bytes(32 * 1024 * 1024 - len(image)))

    def run_entry(self) -> subprocess.CompletedProcess[str]:
        env = os.environ | {'AKHOME': str(self.home), 'OUTFD': '1',
                            'PATH': str(self.bin) + ':' + os.environ['PATH'],
                            'FIXTURE_ROOT': str(self.root), 'FIXTURE_BOOT': str(self.boot)}
        return subprocess.run(['busybox', 'ash', 'anykernel.sh'], cwd=self.home, env=env,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)

    def verify_boot(self, tree: bytes):
        boot = self.boot.read_bytes()
        page = int.from_bytes(boot[36:40], 'little')
        ksize = int.from_bytes(boot[8:12], 'little')
        rsize = int.from_bytes(boot[16:20], 'little')
        second = int.from_bytes(boot[24:28], 'little')
        recovery = int.from_bytes(boot[1632:1636], 'little')
        dsize = int.from_bytes(boot[1648:1652], 'little')
        align = lambda n: (n + page - 1) // page * page
        self.assertEqual(boot[:8], b'ANDROID!')
        self.assertEqual(sha(boot[page:page + ksize]), IMAGE_SHA)
        dtb_pos = page + align(ksize) + align(rsize) + align(second) + align(recovery)
        self.assertEqual(boot[dtb_pos:dtb_pos + dsize], tree)
        self.assertEqual(len(boot), 32 * 1024 * 1024)

    def test_real_2_0_anykernel_core_installs_on_synthetic_boot_and_copies_ksud(self):
        tree = fixture.fdt(b'synthetic-not-the-3.0-reference\0')
        self.make_boot(tree)
        adb = self.fs / 'data/adb'
        adb.mkdir(parents=True)
        (adb / 'ksud').write_bytes(b'previous daemon')
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('ksud OK', p.stdout)
        self.assertIn('Done. Kernel installed.', p.stdout)
        self.assertEqual(sha((adb / 'ksud').read_bytes()), KSUD_SHA)
        self.verify_boot(tree)

    def test_locked_data_skips_ksud_but_installs_on_a_second_synthetic_dtb(self):
        tree = fixture.fdt(b'another-unknown-synthetic-dtb\0')
        self.make_boot(tree)
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('/data is locked - ksud NOT installed', p.stdout)
        self.assertFalse((self.fs / 'data/adb/ksud').exists())
        self.assertIn('Done. Kernel installed.', p.stdout)
        self.verify_boot(tree)


if __name__ == '__main__':
    unittest.main()
