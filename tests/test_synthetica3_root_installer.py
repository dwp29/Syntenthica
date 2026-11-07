#!/usr/bin/env python3
"""Installer UI/guard tests and an opt-in verified-candidate packaging test."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('s3root_pkg_test', ROOT / 'build-kit/scripts/package_synthetica3_root.py')
pkg = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(pkg)


def entry_template() -> bytes:
    entry = (pkg.base.SCRIPTS / 'anykernel.sh').read_bytes()
    entry = pkg.base.replace_once(entry, b'kernel.string=Synthetica 2.0 Experimental - Neutron - MGLRU ON',
                                  b'kernel.string=Synthetica 3.0-rc1 - Neutron - MGLRU ON')
    entry = pkg.base.replace_once(entry, b"'Synthetica 2.0 EXPERIMENTAL - Neutron / MGLRU ON'",
                                  b"'Synthetica 3.0-rc1 TEST - Neutron / MGLRU ON'")
    return pkg.concise_entry(entry)


class InstallerUiTests(unittest.TestCase):
    def test_logo_progress_and_critical_guards(self):
        entry = entry_template()
        self.assertEqual(pkg.base.sha((pkg.base.SCRIPTS / 'prepare-boot.sh').read_bytes()), pkg.base.PREPARE_SHA256)
        self.assertEqual(entry.count(pkg.base.REFERENCE_DTB_SHA256.encode()), 1)
        for required in (
            b'do.devicecheck=1', b'do.modules=0', b'do.systemless=0',
            b'BLOCK=/dev/block/bootdevice/by-name/boot', b'[ -b "$BLOCK" ]',
            b'[ "$partsize" = 134217728 ]', b'[ "$readonly" = 0 ]',
            b'cmp -s "$original" "$BLOCK"', b'conv=fsync',
            b'cmp -s -n "$partsize" "$candidate" "$BLOCK"',
            b'WRITE FAILED. DO NOT REBOOT', b'BOOT READBACK MISMATCH. DO NOT REBOOT',
            b'Backup boot and recovery required.', b'AVB and modules unverified.',
            b'set_progress 0.05', b'set_progress 0.25', b'set_progress 0.70',
            b'set_progress 0.90', b'set_progress 1.0'):
            self.assertIn(required, entry)
        self.assertNotIn(b'/data/adb/ksud', entry)
        lines = pkg.BANNER.decode('ascii').splitlines()
        self.assertEqual(len(lines), 4)
        self.assertLessEqual(max(map(len, lines)), 52)
        self.assertIn('_____', lines[0])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'entry.sh'
            path.write_bytes(entry)
            subprocess.run(['sh', '-n', str(path)], check=True)
            if shutil.which('busybox'):
                subprocess.run(['busybox', 'ash', '-n', str(path)], check=True)

    def test_backend_keeps_checks_but_omits_extra_success_ui(self):
        with zipfile.ZipFile(pkg.base.BASE) as z:
            backend = z.read('META-INF/com/google/android/update-binary')
        start = backend.index(b'debugging() {\n')
        end = backend.index(b'\ncleanup() {\n', start)
        backend = backend[:start] + b'debugging() { :; } # no persistent debug archive\n' + backend[end:]
        backend = pkg.concise_backend(backend)
        for required in (b'ui_printfile banner;', b'do_devicecheck;', b'do_versioncheck;',
                         b'do_levelcheck;', b'do_vendorlevelcheck;', b'ash anykernel.sh;',
                         b'if [ $? != 0 ]; then\n  abort;', b'restore_env;', b'cleanup;',
                         b'show_progress 1.0 0;'):
            self.assertIn(required, backend)
        for removed in (b'AnyKernel3 by osm0sis', b'ui_print "Installing..."', b'ui_print " " "Done!"'):
            self.assertNotIn(removed, backend)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'update-binary'
            path.write_bytes(backend)
            subprocess.run(['sh', '-n', str(path)], check=True)
            if shutil.which('busybox'):
                subprocess.run(['busybox', 'ash', '-n', str(path)], check=True)

    def test_readme_retains_safety_and_unverified_status(self):
        text = pkg.readme('a' * 64, 'b' * 64)
        for required in ('BUKAN RILIS STABIL', 'belum diuji', 'belum terbukti',
                         'Installer tidak membuat backup otomatis', 'JANGAN REBOOT',
                         'signature boot masih valid', 'kamera', 'vbmeta',
                         pkg.build.EXPECTED_RELEASE):
            self.assertIn(required, text)


@unittest.skipUnless(shutil.which('busybox'), 'host BusyBox needed for mocked writer')
class MockedWriterTests(unittest.TestCase):
    """Exercise the exact writer control flow, using regular files and stub tools.

    The type and size checks are changed only in the disposable test copy. This
    does not test real recovery, MagiskBoot, AVB or a physical block device.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t = Path(self.temp.name)
        self.home = self.t / 'home'
        (self.home / 'tools').mkdir(parents=True)
        self.bin = self.t / 'bin'
        self.bin.mkdir()
        self.target = self.t / 'boot.img'
        self.original = b'A' * 4096
        self.target.write_bytes(self.original)
        (self.home / 'payload').write_bytes(b'B' * 4096)
        (self.home / 'Image.gz').write_bytes(b'unused fixture')
        (self.home / 'tools/magiskboot').write_text('unused fixture')
        (self.bin / 'ash').symlink_to(shutil.which('busybox'))
        getprop = self.bin / 'getprop'
        getprop.write_text('''#!/bin/sh
case "$1" in
  ro.boot.slot_suffix) echo "${MOCK_SLOT-}" ;;
  ro.boot.flash.locked) echo "${MOCK_LOCKED-0}" ;;
  ro.boot.verifiedbootstate) echo "${MOCK_VERIFIED-}" ;;
  ro.boot.vbmeta.device_state) echo "${MOCK_DEVICE_STATE-}" ;;
esac
''')
        getprop.chmod(0o755)
        busy = self.home / 'tools/busybox'
        busy.write_text('''#!/bin/sh
case "$1" in
  blockdev)
    case "$2" in
      --getsize64) echo "${MOCK_PARTSIZE-4096}"; exit 0 ;;
      --getro) echo "${MOCK_READONLY-0}"; exit 0 ;;
    esac ;;
  dd)
    case " $* " in
      *" of=$MOCK_BLOCK "*) [ "$MOCK_MODE" = writefail ] && exit 1 ;;
    esac ;;
  cmp)
    if [ "$MOCK_MODE" = readbackfail ] && [ "$2" = -s ] && [ "$3" = -n ]; then exit 1; fi ;;
esac
exec /usr/bin/busybox "$@"
''')
        busy.chmod(0o755)
        prep = self.home / 'tools/prepare-boot.sh'
        prep.write_text('''#!/bin/sh
if [ "$MOCK_MODE" = preparefail ]; then
  echo 'PREPARE FAILED: fixture DTB rejected' >&2
  exit 1
fi
cp "$AKHOME/payload" "$3"
''')
        prep.chmod(0o755)
        entry = entry_template().decode()
        entry = entry.replace('BLOCK=/dev/block/bootdevice/by-name/boot', 'BLOCK="$MOCK_BLOCK"', 1)
        entry = entry.replace('[ -b "$BLOCK" ]', '[ -f "$BLOCK" ]', 1)
        entry = entry.replace('[ "$partsize" = 134217728 ]', '[ "$partsize" = 4096 ]', 1)
        self.entry = self.t / 'test-entry.sh'
        self.entry.write_text(entry)

    def run_writer(self, **extra):
        env = os.environ | {'AKHOME': str(self.home), 'OUTFD': '1', 'MOCK_BLOCK': str(self.target),
                            'MOCK_MODE': '', 'PATH': str(self.bin) + ':' + os.environ['PATH']} | extra
        return subprocess.run(['busybox', 'ash', str(self.entry)], env=env, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)

    def test_success_writes_then_verifies_with_minimal_progress(self):
        p = self.run_writer()
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertEqual(self.target.read_bytes(), b'B' * 4096)
        self.assertIn('AVB and modules unverified.', p.stdout)
        self.assertIn('Verifying write...', p.stdout)
        self.assertIn('Boot write and byte readback completed.', p.stdout)
        self.assertIn('set_progress 1.0', p.stdout)
        self.assertNotIn('PREPARE FAILED:', p.stdout)

    def test_preconditions_fail_before_any_write(self):
        for env, message in (({'MOCK_SLOT': '_a'}, 'A/B slot detected'),
                             ({'MOCK_LOCKED': '1'}, 'Bootloader reports locked'),
                             ({'MOCK_LOCKED': ''}, 'Cannot confirm unlocked bootloader'),
                             ({'MOCK_PARTSIZE': '8192'}, 'Boot partition size differs'),
                             ({'MOCK_READONLY': '1'}, 'Boot partition is read-only')):
            with self.subTest(env=env):
                self.target.write_bytes(self.original)
                p = self.run_writer(**env)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)
                self.assertEqual(self.target.read_bytes(), self.original)
                self.assertNotIn('Writing boot...', p.stdout)

    def test_prepare_failure_reports_reason_and_never_writes(self):
        p = self.run_writer(MOCK_MODE='preparefail')
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('PREPARE FAILED: fixture DTB rejected', p.stdout)
        self.assertIn('boot partition was not written', p.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.assertNotIn('Writing boot...', p.stdout)

    def test_write_and_readback_failures_say_do_not_reboot(self):
        for mode, message in (('writefail', 'WRITE FAILED. DO NOT REBOOT'),
                              ('readbackfail', 'BOOT READBACK MISMATCH. DO NOT REBOOT')):
            with self.subTest(mode=mode):
                self.target.write_bytes(self.original)
                p = self.run_writer(MOCK_MODE=mode)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)
                self.assertNotIn('set_progress 1.0', p.stdout)
                self.assertNotIn('Boot write and byte readback completed.', p.stdout)


class CandidatePackageTests(unittest.TestCase):
    def setUp(self):
        result, config = os.environ.get('S3ROOT_EVIDENCE_DIR'), os.environ.get('S3RC_TESTED_CONFIG')
        if not result or not config:
            self.skipTest('S3ROOT_EVIDENCE_DIR and S3RC_TESTED_CONFIG required for candidate packaging')
        self.result, self.config = Path(result), Path(config)
        if not self.result.is_dir() or not self.config.is_file():
            self.fail('candidate evidence or tested config missing')
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)

    def test_reproducibility_integrity_and_safety_metadata(self):
        a, b = self.work / 'a.zip', self.work / 'b.zip'
        info = pkg.package(self.result, self.config, a)
        pkg.package(self.result, self.config, b)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        with zipfile.ZipFile(a) as z:
            self.assertIsNone(z.testzip())
            self.assertEqual(set(z.namelist()), set(pkg.base.BASE_FILES) | {
                'Image.gz', 'anykernel.sh', 'tools/prepare-boot.sh', 'README-FLASH.txt', 'BUILD-INFO.json', 'banner'})
            meta = json.loads(z.read('BUILD-INFO.json'))
            self.assertEqual(meta['release'], pkg.build.EXPECTED_RELEASE)
            self.assertEqual(meta['manager_exec_fd_patch_sha256'], pkg.build.PATCH_SHA256)
            self.assertEqual(meta['image_sha256'], info['image_sha256'])
            self.assertFalse(meta['auto_backup'])
            entry = z.read('anykernel.sh')
            self.assertEqual(entry.count(meta['image_sha256'].encode()), 1)
            self.assertEqual(entry.count(pkg.base.REFERENCE_DTB_SHA256.encode()), 1)
            self.assertEqual(z.read('banner'), pkg.BANNER)
            for name in ('anykernel.sh', 'tools/prepare-boot.sh', 'META-INF/com/google/android/update-binary'):
                path = self.work / Path(name).name
                path.write_bytes(z.read(name))
                subprocess.run(['busybox', 'ash', '-n', str(path)], check=True)
            self.assertFalse(any(n.endswith(('.pem', '.key', '.ko')) for n in z.namelist()))

    def test_missing_patch_evidence_or_tampered_image_fails_closed(self):
        copied = self.work / 'evidence'
        shutil.copytree(self.result, copied)
        out = self.work / 'should-not-exist.zip'
        path = copied / 'STATUS.json'
        original = path.read_bytes()
        status = json.loads(original)
        status['manager_exec_fd_patch_sha256'] = '0' * 64
        path.write_text(json.dumps(status))
        with self.assertRaises(ValueError):
            pkg.package(copied, self.config, out)
        self.assertFalse(out.exists())
        path.write_bytes(original)
        image = copied / 'Image.gz.DO-NOT-FLASH'
        with image.open('ab') as f:
            f.write(b'tampered')
        with self.assertRaises(ValueError):
            pkg.package(copied, self.config, out)
        self.assertFalse(out.exists())


if __name__ == '__main__':
    unittest.main()
