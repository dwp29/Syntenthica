"""ARM/QEMU integration tests on synthetic boot files, never a device.

Opt in with S2_QEMU_INTEGRATION=1 and provide S2_IMAGE, S2_ARM_BB,
S2_ARM_MAGISKBOOT and S2_AVBTOOL. Requires qemu-arm-static, cpio and lz4.
"""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_synthetica3_boot as audit

spec = importlib.util.spec_from_file_location('bootfixture', ROOT / 'tests/test_synthetica3_boot.py')
fixture = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(fixture)
PREPARE = ROOT / 'build-kit/ci/synthetica2-experimental/test-installer/prepare-boot.sh'


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@unittest.skipUnless(os.environ.get('S2_QEMU_INTEGRATION') == '1', 'QEMU integration is opt-in')
class SyntheticRepackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t = Path(self.temp.name)
        self.image = Path(os.environ['S2_IMAGE']).resolve()
        self.arm_bb = Path(os.environ['S2_ARM_BB']).resolve()
        self.arm_mb = Path(os.environ['S2_ARM_MAGISKBOOT']).resolve()
        self.avbtool = Path(os.environ['S2_AVBTOOL']).resolve()
        for p in (self.image, self.arm_bb, self.arm_mb, self.avbtool):
            self.assertTrue(p.is_file(), str(p))
        self.bb = self.wrapper('bb', self.arm_bb)
        self.mb = self.wrapper('mb', self.arm_mb)
        self.tree = fixture.fdt()
        self.kernel_hash = digest(self.image)
        self.dtb_hash = hashlib.sha256(self.tree).hexdigest()
        self.original = self.make_boot('stock', magisk=False)
        self.original_hash = digest(self.original)

    def wrapper(self, name: str, binary: Path, tamper: str | None = None) -> Path:
        p = self.t / name
        command = 'qemu-arm-static ' + shlex.quote(str(binary))
        if tamper:
            # Corrupt the repacked synthetic file only, after a successful repack.
            assert tamper in ('header', 'avb')
            code = ("p=__import__('sys').argv[1];f=open(p,'r+b');"
                    + ("f.seek(44);f.write(b'\\x00');" if tamper == 'header' else
                       "f.seek(-44,2);o=int.from_bytes(f.read(8),'big');f.seek(o+120);b=f.read(1);f.seek(o+120);f.write(bytes([b[0]^1]));")
                    + "f.close()")
            p.write_text('#!/bin/sh\nif [ "$1" = repack ]; then\n' + command + ' "$@" || exit $?\n'
                         + 'python3 -c ' + shlex.quote(code) + ' "$4"\nexit $?\nfi\nexec ' + command + ' "$@"\n')
        else:
            p.write_text('#!/bin/sh\nexec ' + command + ' "$@"\n')
        p.chmod(0o755)
        return p

    def make_boot(self, name: str, *, magisk: bool, partition_bytes: int = 32 * 1024 * 1024) -> Path:
        rd = self.t / ('rd-' + name)
        rd.mkdir()
        (rd / 'init').write_bytes(b'#!/bin/sh\nexit 0\n')
        names = ['init']
        if magisk:
            (rd / '.backup').mkdir()
            (rd / '.backup/.magisk').write_text('KEEPVERITY=true\n')
            (rd / 'init.magisk.rc').write_text('on init\n')
            names += ['.backup', '.backup/.magisk', 'init.magisk.rc']
        cpio = subprocess.run(['cpio', '-o', '-H', 'newc', '--quiet'], cwd=rd,
                              input=('\n'.join(names)+'\n').encode(), stdout=subprocess.PIPE, check=True).stdout
        compressed = subprocess.run(['lz4', '-l', '-z', '-c'], input=cpio, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, check=True).stdout
        path = self.t / (name + '.img')
        path.write_bytes(fixture.boot(kernel=b'old synthetic kernel', ramdisk=compressed, tree=self.tree))
        subprocess.run(['python3', str(self.avbtool), 'add_hash_footer', '--image', str(path),
                        '--partition_size', str(partition_bytes), '--partition_name', 'boot'], check=True)
        return path

    def prepare(self, name: str, *, original: Path | None = None, kernel: Path | None = None,
                dtb_hash: str | None = None, kernel_hash: str | None = None, mb: Path | None = None):
        output = self.t / (name + '-out.img')
        work = self.t / (name + '-work')
        env = os.environ | {'BB': str(self.bb), 'MAGISKBOOT': str(mb or self.mb)}
        p = subprocess.run(['qemu-arm-static', str(self.arm_bb), 'ash', str(PREPARE),
                            str(original or self.original), str(kernel or self.image), str(output), str(work),
                            kernel_hash or self.kernel_hash, dtb_hash or self.dtb_hash],
                           env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        self.assertEqual(digest(self.original), self.original_hash, 'source synthetic boot was modified')
        return p, output

    def test_repack_preserves_sections_header_and_vbmeta_bytes(self):
        p, output = self.prepare('good')
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertTrue(output.is_file())
        old, new = audit.inspect_boot(self.original), audit.inspect_boot(output)
        comparison = audit.compare_boot(old, new, self.kernel_hash)
        self.assertTrue(all(comparison['stable_header_fields_match'].values()), comparison)
        self.assertTrue(all(comparison['non_kernel_sections_match'].values()), comparison)
        self.assertTrue(comparison['candidate_kernel_equals_bundle_image'])
        self.assertTrue(comparison['candidate_legacy_boot_id_matches'])
        self.assertTrue(new['avb']['footer_at_end'])
        self.assertIn('AVB SIGNATURE, ROM MODULES, KERNEL BOOT AND ROOT ARE NOT VERIFIED', p.stdout)

    def test_wrong_kernel_or_reference_dtb_is_rejected(self):
        for name, kwargs, message in (
                ('bad-kernel', {'kernel_hash': '0' * 64}, 'kernel SHA-256 mismatch'),
                ('bad-dtb', {'dtb_hash': '0' * 64}, 'boot DTB is not the known Lunaris')):
            with self.subTest(name=name):
                p, output = self.prepare(name, **kwargs)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)
                self.assertFalse(output.exists())

    def test_detected_magisk_ramdisk_is_rejected(self):
        original = self.make_boot('magisk', magisk=True)
        p, output = self.prepare('magisk-check', original=original)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Magisk or unsupported ramdisk', p.stdout)
        self.assertFalse(output.exists())

    def test_corrupted_repacked_header_and_vbmeta_are_rejected(self):
        for kind, message in (('header', 'boot header changed unexpectedly'), ('avb', 'embedded AVB metadata changed')):
            with self.subTest(kind=kind):
                wrapper = self.wrapper('mb-' + kind, self.arm_mb, tamper=kind)
                p, _ = self.prepare('tamper-' + kind, mb=wrapper)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)

    @unittest.skipUnless(os.environ.get('S2_LOOP_WRITER') == '1', 'loop-backed writer integration is opt-in')
    def test_loop_backed_writer_round_trip(self):
        # CI-only. Never touch an existing /dev/block path or an unverified loop device.
        if os.geteuid() != 0:
            self.skipTest('loop fixture requires root')
        target = Path('/dev/block/bootdevice/by-name/boot')
        if target.exists() or target.is_symlink():
            self.skipTest('real or preexisting boot path exists; refusing to touch it')
        backing = self.make_boot('loop-fixture', magisk=False, partition_bytes=134217728)
        before = audit.inspect_boot(backing)
        attach = subprocess.run(['losetup', '--find', '--show', str(backing)], text=True,
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if attach.returncode:
            self.skipTest('loop devices unavailable: ' + attach.stderr.strip())
        loop = attach.stdout.strip()
        created = []
        try:
            actual = subprocess.run(['losetup', '--noheadings', '--output', 'BACK-FILE', loop],
                                    check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
            self.assertEqual(Path(actual).resolve(), backing.resolve(), 'loop does not reference our fixture')
            for d in (Path('/dev/block'), Path('/dev/block/bootdevice'), target.parent):
                if not d.exists():
                    d.mkdir()
                    created.append(d)
            target.symlink_to(loop)
            home = self.t / 'recovery-home'
            tools, bindir = home / 'tools', home / 'bin'
            tools.mkdir(parents=True)
            bindir.mkdir()
            shutil.copy(self.bb, tools / 'busybox')
            shutil.copy(self.mb, tools / 'magiskboot')
            shutil.copy(PREPARE, tools / 'prepare-boot.sh')
            shutil.copy(self.image, home / 'Image.gz')
            (bindir / 'ash').symlink_to(shutil.which('busybox'))
            prop = bindir / 'getprop'
            prop.write_text('#!/bin/sh\n[ "$1" = ro.boot.flash.locked ] && echo 0\nexit 0\n')
            prop.chmod(0o755)
            entry = (ROOT / 'build-kit/ci/synthetica2-experimental/test-installer/anykernel.sh').read_text()
            reference = '6ae7105b5ad512e40af1f14e53a8c27010b2d7caf0934d53c58cfcc24cc3f239'
            self.assertEqual(entry.count(reference), 1)
            (home / 'test-anykernel.sh').write_text(entry.replace(reference, self.dtb_hash))
            env = os.environ | {'AKHOME': str(home), 'OUTFD': '1', 'PATH': str(bindir) + ':' + os.environ['PATH']}
            p = subprocess.run(['busybox', 'ash', str(home / 'test-anykernel.sh')], env=env,
                               text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(p.returncode, 0, p.stdout)
            self.assertIn('Boot write and byte readback completed', p.stdout)
            after = audit.inspect_boot(backing)
            comparison = audit.compare_boot(before, after, self.kernel_hash)
            self.assertTrue(all(comparison['stable_header_fields_match'].values()), comparison)
            self.assertTrue(all(comparison['non_kernel_sections_match'].values()), comparison)
            self.assertTrue(comparison['candidate_kernel_equals_bundle_image'])
        finally:
            if target.is_symlink() and os.readlink(target) == loop:
                target.unlink()
            subprocess.run(['losetup', '--detach', loop], check=True)
            for d in reversed(created):
                d.rmdir()

    def test_missing_footer_or_wrong_header_is_rejected_before_output(self):
        raw = bytearray(self.original.read_bytes())
        for kind, change, message in (
                ('header-version', lambda a: a.__setitem__(40, 3), 'only Android boot header v2'),
                ('no-avb-footer', lambda a: a.__setitem__(slice(-64, -60), b'NOPE'), 'missing AVB footer')):
            with self.subTest(kind=kind):
                broken = bytearray(raw)
                change(broken)
                path = self.t / (kind + '-source.img')
                path.write_bytes(broken)
                before = digest(path)
                p, output = self.prepare(kind, original=path)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)
                self.assertFalse(output.exists())
                self.assertEqual(digest(path), before)


if __name__ == '__main__':
    unittest.main()
