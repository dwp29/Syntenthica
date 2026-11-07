#!/usr/bin/env python3
"""Root/loop-device synthetic integration. Refuses existing Android boot paths."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat_loop_fixture', ROOT / 'tests/test_synthetica3_boot.py')
fixture = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fixture)
TARGET = Path('/dev/block/bootdevice/by-name/boot')


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        while data := f.read(1024 * 1024):
            h.update(data)
    return h.hexdigest()


@unittest.skipUnless(os.environ.get('S3_COMPAT_LOOP') == '1', 'loop integration is opt-in')
class SyntheticLoopTests(unittest.TestCase):
    def test_audit_and_unknown_dtb_rejection_never_write_loop_boot(self):
        if os.geteuid() != 0:
            self.skipTest('loop integration requires root')
        if TARGET.exists() or TARGET.is_symlink():
            self.skipTest('preexisting boot path; refusing to touch it')
        for path in (Path('/dev/block/bootdevice/by-name/boot_a'), Path('/dev/block/bootdevice/by-name/boot_b'),
                     Path('/dev/block/by-name/boot_a'), Path('/dev/block/by-name/boot_b')):
            if path.exists() or path.is_symlink():
                self.skipTest('preexisting slotted boot name; refusing to touch it')
        arm_bb = Path(os.environ['S3_ARM_BB']).resolve()
        arm_mb = Path(os.environ['S3_ARM_MAGISKBOOT']).resolve()
        image = Path(os.environ['S3_IMAGE']).resolve()
        entry = Path(os.environ['S3_ANYKERNEL']).resolve()
        avbtool = Path(os.environ['S3_AVBTOOL']).resolve()
        for path in (arm_bb, arm_mb, image, entry, avbtool):
            self.assertTrue(path.is_file(), str(path))
        with tempfile.TemporaryDirectory(prefix='compat-loop-ci-') as tmp:
            t = Path(tmp)
            tree = fixture.fdt()
            expected = hashlib.sha256(tree).hexdigest()
            backing = t / 'synthetic-only.img'
            backing.write_bytes(fixture.boot(kernel=b'synthetic old kernel', tree=tree))
            subprocess.run(['python3', str(avbtool), 'add_hash_footer', '--image', str(backing),
                            '--partition_size', '134217728', '--partition_name', 'boot'], check=True)
            before = digest(backing)
            attach = subprocess.run(['losetup', '--find', '--show', str(backing)], text=True,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if attach.returncode:
                self.skipTest('loop devices unavailable: ' + attach.stderr.strip())
            loop = attach.stdout.strip()
            created = []
            try:
                actual = subprocess.run(['losetup', '--noheadings', '--output', 'BACK-FILE', loop],
                                        text=True, stdout=subprocess.PIPE, check=True).stdout.strip()
                self.assertEqual(Path(actual).resolve(), backing.resolve(), 'loop must reference our fixture')
                for directory in (Path('/dev/block'), Path('/dev/block/bootdevice'), TARGET.parent):
                    if not directory.exists():
                        directory.mkdir()
                        created.append(directory)
                TARGET.symlink_to(loop)
                home, bindir = t / 'home', t / 'bin'
                (home / 'tools').mkdir(parents=True)
                bindir.mkdir()
                bb = bindir / 'busybox'
                bb.write_text('#!/bin/sh\nexec qemu-arm-static ' + shlex.quote(str(arm_bb)) + ' "$@"\n')
                bb.chmod(0o755)
                (bindir / 'ash').symlink_to(shutil.which('busybox'))
                getprop = bindir / 'getprop'
                getprop.write_text('#!/bin/sh\n[ "$1" = ro.boot.flash.locked ] && echo 0\nexit 0\n')
                getprop.chmod(0o755)
                mb = home / 'tools/magiskboot'
                mb.write_text('#!/bin/sh\nexec qemu-arm-static ' + shlex.quote(str(arm_mb)) + ' "$@"\n')
                mb.chmod(0o755)
                shutil.copy(bb, home / 'tools/busybox')
                shutil.copy(image, home / 'Image.gz')
                shutil.copy(ROOT / 'build-kit/ci/synthetica2-experimental/test-installer/prepare-boot.sh',
                            home / 'tools/prepare-boot.sh')
                env = os.environ | {'AKHOME': str(home), 'OUTFD': '1', 'PATH': str(bindir) + ':/usr/bin:/bin'}
                audit = ROOT / 'build-kit/ci/synthetica3-compat/boot-audit.sh'
                p = subprocess.run(['qemu-arm-static', str(arm_bb), 'ash', str(audit), '3', '1',
                                    str(t / 'missing.zip')], env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=90)
                self.assertEqual(p.returncode, 0, p.stdout)
                parts = re.findall(r'DTB SHA256 [12]/2: ([0-9a-f]{32})', p.stdout)
                self.assertEqual(''.join(parts), expected)
                self.assertEqual(digest(backing), before, 'read-only audit changed loop boot')
                p = subprocess.run(['busybox', 'ash', str(entry)], env=env, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn('boot DTB is not the known Lunaris 3.13 reference', p.stdout)
                self.assertIn('DTB SHA256 1/2: ' + expected[:32], p.stdout)
                self.assertIn('DTB SHA256 2/2: ' + expected[32:], p.stdout)
                self.assertIn('boot partition was not written', p.stdout)
                self.assertNotIn('Writing boot...', p.stdout)
                self.assertEqual(digest(backing), before, 'rejected installer changed loop boot')
            finally:
                if TARGET.is_symlink() and os.readlink(TARGET) == loop:
                    TARGET.unlink()
                subprocess.run(['losetup', '--detach', loop], check=True)
                for directory in reversed(created):
                    directory.rmdir()


if __name__ == '__main__':
    unittest.main()
