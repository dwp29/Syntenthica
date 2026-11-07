#!/usr/bin/env python3
"""Synthetic tests: no test reads or writes a phone or a real boot partition."""
from __future__ import annotations

import gzip
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import struct
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


pkg = load('compat_pkg', ROOT / 'build-kit/scripts/package_synthetica3_compat.py')
config_guard = load('compat_config_guard', ROOT / 'build-kit/scripts/build_synthetica3.py')
fixture = load('compat_boot_fixture', ROOT / 'tests/test_synthetica3_boot.py')
previous = load('compat_previous_tests', ROOT / 'tests/test_synthetica3_root_installer.py')
AUDIT = ROOT / 'build-kit/ci/synthetica3-compat/boot-audit.sh'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config_in_pinned_image(image_gz: bytes) -> bytes:
    """Read IKCONFIG only after the containing ZIP was verified against its pin."""
    raw = gzip.decompress(image_gz)
    start, end = b'IKCFG_ST', b'IKCFG_ED'
    if raw.count(start) != 1 or raw.count(end) != 1:
        raise ValueError('missing or ambiguous embedded config markers')
    a, b = raw.index(start) + len(start), raw.index(end)
    if b <= a or b - a > 4 * 1024 * 1024:
        raise ValueError('unexpected embedded config length')
    return gzip.decompress(raw[a:b])


class Released20ComparisonTests(unittest.TestCase):
    """Compare the actual, SHA-pinned 2.0 release without running its scripts."""

    @classmethod
    def setUpClass(cls):
        archive = (ROOT / 'release/Synthetica-2.0.zip').read_bytes()
        if hashlib.sha256(archive).hexdigest() != previous.pkg.base.BASE_SHA256:
            raise AssertionError('2.0 release ZIP does not match its pinned digest')
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            if z.testzip() is not None or len(z.namelist()) != len(set(z.namelist())):
                raise AssertionError('invalid 2.0 release ZIP')
            cls.names = set(z.namelist())
            cls.entry = z.read('anykernel.sh')
            cls.core = z.read('tools/ak3-core.sh')
            cls.image = z.read('Image.gz')

    def test_compat_candidate_recognizes_the_same_device_names_as_20(self):
        names = lambda data: set(re.findall(rb'^device\.name\d+=([a-z0-9_]+)$', data, re.M))
        release_names = names(self.entry)
        candidate = pkg.compat_entry(previous.entry_template())
        self.assertEqual(release_names, {b'joyeuse', b'curtana', b'excalibur', b'gram', b'miatoll'})
        self.assertEqual(names(candidate), release_names)
        # Recognition alone is not boot approval: the strict DTB guard stays.
        self.assertEqual(candidate.count(pkg.REFERENCE_DTB.encode()), 1)
        self.assertIn(b'cmp -s -n "$partsize" "$candidate" "$BLOCK"', candidate)

    def test_20_dtb_and_ksud_behaviour_is_not_kernel_only(self):
        self.assertTrue({'dtb', 'dtb.img', 'dtbo', 'dtbo.img'}.isdisjoint(self.names))
        self.assertIn('ksud', self.names)
        self.assertIn(b'cp -f ./ksud /data/adb/ksud;', self.entry)
        self.assertLess(self.entry.index(b'cp -f ./ksud'), self.entry.index(b'dump_boot;'))
        self.assertIn(b'PATCH_VBMETA_FLAG=auto;', self.entry)
        self.assertIn(b'magiskboot dtb $fdt patch', self.core)
        self.assertIn(b'flash_generic dtbo;', self.core)

    def test_20_image_embeds_stock_defconfig_not_the_recorded_build_config(self):
        self.assertEqual(hashlib.sha256(self.image).hexdigest(),
                         '58a57b1fcca0eb6190c836f8c89d7c5a514b1c395e85c2770ab1c43173887fff')
        embedded = config_in_pinned_image(self.image)
        baseline = (ROOT / 'artifacts/generated.config.txt').read_bytes()
        self.assertEqual(hashlib.sha256(embedded).hexdigest(),
                         '8188e2539466a3e6797e98dd704b4b5a8e6439b21c08ba8d2a82b2829a8b190d')
        self.assertEqual(hashlib.sha256(baseline).hexdigest(),
                         '248af9218b5ed9dd82202956d99991f97428c3010565a810eac3c9e6f71ff33b')
        self.assertNotEqual(embedded, baseline)
        self.assertIn(b'CONFIG_LOCALVERSION="-perf"', embedded)
        self.assertIn(b'CONFIG_LOCALVERSION="-Synthetica-2.0"', baseline)


@unittest.skipUnless(shutil.which('busybox'), 'host BusyBox required')
class CompatWriterTests(previous.MockedWriterTests):
    """Re-use original writer regression tests with the compatibility entry."""
    def setUp(self):
        super().setUp()
        entry = pkg.compat_entry(previous.entry_template()).decode()
        entry = entry.replace('BLOCK=/dev/block/bootdevice/by-name/boot', 'BLOCK="$MOCK_BLOCK"', 1)
        entry = entry.replace('[ -b "$BLOCK" ]', '[ -f "$BLOCK" ]', 1)
        entry = entry.replace('[ "$partsize" = 134217728 ]', '[ "$partsize" = 4096 ]', 1)
        self.dir1, self.dir2 = self.t / 'by-name1', self.t / 'by-name2'
        self.dir1.mkdir()
        self.dir2.mkdir()
        entry = entry.replace('for dir in /dev/block/bootdevice/by-name /dev/block/by-name;',
                              f'for dir in {self.dir1} {self.dir2};', 1)
        self.cmdline = self.t / 'cmdline'
        self.cmdline.write_text('quiet console=ttyS0\n')
        entry = entry.replace('cat /proc/cmdline 2>/dev/null', f'cat {self.cmdline} 2>/dev/null', 1)
        self.entry.write_text(entry)
        prop = self.bin / 'getprop'
        prop.write_text('''#!/bin/sh
case "$1" in
  ro.boot.slot_suffix) echo "${MOCK_SLOT-}" ;;
  ro.boot.slot) echo "${MOCK_SLOT_NAME-}" ;;
  ro.build.ab_update) echo "${MOCK_AB-}" ;;
  ro.boot.flash.locked) echo "${MOCK_LOCKED-0}" ;;
  ro.boot.verifiedbootstate) echo "${MOCK_VERIFIED-}" ;;
  ro.boot.vbmeta.device_state) echo "${MOCK_DEVICE_STATE-}" ;;
esac
''')
        prop.chmod(0o755)
        prep = self.home / 'tools/prepare-boot.sh'
        prep.write_text('''#!/bin/sh
case "$MOCK_MODE" in
  preparefail) echo 'PREPARE FAILED: fixture DTB rejected' >&2; exit 1 ;;
  dtbfail)
    mkdir -p "$AKHOME/boot-check/orig"
    printf 'synthetic fixture dtb' > "$AKHOME/boot-check/orig/dtb"
    echo 'PREPARE FAILED: boot DTB is not the known Lunaris 3.13 reference' >&2
    exit 1 ;;
  unexpected) echo 'fixture executable could not start' >&2; exit 1 ;;
esac
cp "$AKHOME/payload" "$3"
''')
        prep.chmod(0o755)

    def test_additional_slot_indications_reject_before_writes(self):
        for env in ({'MOCK_SLOT_NAME': 'a'}, {'MOCK_SLOT_NAME': '_b'},
                    {'MOCK_AB': 'true'}, {'MOCK_AB': '1'}, {'MOCK_AB': 'unexpected'}):
            with self.subTest(env=env):
                self.target.write_bytes(self.original)
                p = self.run_writer(**env)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn('no boot selected', p.stdout)
                self.assertNotIn('Writing boot...', p.stdout)
                self.assertEqual(self.target.read_bytes(), self.original)
        self.cmdline.write_text('console=ttyS0 androidboot.slot_suffix=_a\n')
        p = self.run_writer()
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('A/B slot in kernel command line', p.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)
        self.cmdline.write_text('quiet\n')
        (self.dir2 / 'boot_b').symlink_to('missing-device')
        p = self.run_writer()
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Slotted boot names detected', p.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_rejected_dtb_prints_fingerprint_without_writing(self):
        p = self.run_writer(MOCK_MODE='dtbfail')
        self.assertNotEqual(p.returncode, 0, p.stdout)
        expected = hashlib.sha256(b'synthetic fixture dtb').hexdigest()
        self.assertIn('DTB SHA256 1/2: ' + expected[:32], p.stdout)
        self.assertIn('DTB SHA256 2/2: ' + expected[32:], p.stdout)
        self.assertIn('boot partition was not written', p.stdout)
        self.assertNotIn('Writing boot...', p.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)

    def test_unexpected_prepare_failure_is_visible(self):
        p = self.run_writer(MOCK_MODE='unexpected')
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Preparation failed unexpectedly; save recovery.log.', p.stdout)
        self.assertEqual(self.target.read_bytes(), self.original)


@unittest.skipUnless(shutil.which('busybox'), 'host BusyBox required')
class AuditScriptTests(unittest.TestCase):
    """Execute a test copy with paths/type checks redirected to regular fixtures.

    The source code itself has no test-mode override or regular-file boot path.
    """
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t = Path(self.temp.name)
        self.base, self.other = self.t / 'primary', self.t / 'secondary'
        self.base.mkdir()
        self.other.mkdir()
        self.work = self.t / 'tmp'
        self.work.mkdir()
        self.bin = self.t / 'bin'
        self.bin.mkdir()
        self.cmdline = self.t / 'cmdline'
        self.cmdline.write_text('quiet console=ttyS0\n')
        self.tree = fixture.fdt()
        self.boot = self.base / 'boot'
        self.make_boot()
        script = AUDIT.read_text()
        for old, new in (
            ('WORK_BASE=/tmp', f'WORK_BASE={shlex.quote(str(self.work))}'),
            ('CMDLINE=/proc/cmdline', f'CMDLINE={shlex.quote(str(self.cmdline))}'),
            ('PRIMARY=/dev/block/bootdevice/by-name', f'PRIMARY={shlex.quote(str(self.base))}'),
            ('SECONDARY=/dev/block/by-name', f'SECONDARY={shlex.quote(str(self.other))}'),
            # BusyBox ash may resolve its own applet before the fixture in PATH.
            # Pin the test fallback explicitly; the ZIP-extraction path remains unchanged.
            ('BB=$(command -v busybox)', f'BB={shlex.quote(str(self.bin / "busybox"))}'),
            ('[ ! -b "$BLOCK" ]', '[ ! -f "$BLOCK" ]'),
            ('[ -b "$BLOCK" ]', '[ -f "$BLOCK" ]'),
        ):
            self.assertEqual(script.count(old), 1, old)
            script = script.replace(old, new, 1)
        self.script = self.t / 'boot-audit.sh'
        self.script.write_text(script)
        prop = self.bin / 'getprop'
        prop.write_text('''#!/bin/sh
case "$1" in
  ro.product.device) echo "${PROP_DEVICE-joyeuse}" ;;
  ro.build.product) echo "${PROP_PRODUCT-}" ;;
  ro.product.vendor.device) echo "${PROP_VENDOR_DEVICE-}" ;;
  ro.vendor.product.device) echo "${PROP_VENDOR_PRODUCT-}" ;;
  ro.boot.slot_suffix) echo "${PROP_SUFFIX-}" ;;
  ro.boot.slot) echo "${PROP_SLOT-}" ;;
  ro.build.ab_update) echo "${PROP_AB-}" ;;
  ro.boot.flash.locked) echo "${PROP_LOCKED-0}" ;;
  ro.boot.verifiedbootstate) echo "${PROP_VERIFIED-orange}" ;;
  ro.boot.vbmeta.device_state) echo "${PROP_DEVICE_STATE-unlocked}" ;;
esac
''')
        prop.chmod(0o755)
        host_busybox = shutil.which('busybox')
        assert host_busybox
        self.wrapper_bb(host_busybox)
        self.shell = [host_busybox, 'ash']

    def wrapper_bb(self, command: str):
        wrapper = self.bin / 'busybox'
        wrapper.write_text('''#!/bin/sh
if [ "$1" = blockdev ] && [ "$2" = --getsize64 ]; then
  stat -c %s "$3"
  exit $?
fi
if [ "$1" = dd ] && [ "${SHORT_DTB-}" = 1 ]; then
  for arg in "$@"; do
    case "$arg" in of=*/dtb.bin) printf X > "${arg#of=}"; exit 0;; esac
  done
fi
exec ''' + shlex.quote(command) + ''' "$@"
''')
        wrapper.chmod(0o755)

    def make_boot(self, *, tree: bytes | None = None, second: bytes = b'second',
                  recovery: bytes = b'recovery'):
        self.tree = fixture.fdt() if tree is None else tree
        data = fixture.boot(tree=self.tree, second=second, recovery=recovery)
        self.boot.write_bytes(data + b'\0' * (16 * 1024 * 1024 - len(data)))

    def audit(self, *, bundle: Path | None = None, **extra):
        env = os.environ | {'PATH': str(self.bin) + ':/usr/bin:/bin'} | extra
        zip_path = bundle if bundle is not None else self.t / 'missing.zip'
        return subprocess.run(self.shell + [str(self.script), '3', '1', str(zip_path)],
                              env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                              text=True, timeout=30)

    def assert_read_only(self, before: str):
        self.assertEqual(sha(self.boot), before)
        self.assertEqual(list(self.work.iterdir()), [], 'private temporary DTB was not cleaned')

    def test_reports_raw_section_hash_with_recovery_and_second_sections(self):
        before = sha(self.boot)
        p = self.audit()
        self.assertEqual(p.returncode, 0, p.stdout)
        parts = re.findall(r'DTB SHA256 [12]/2: ([0-9a-f]{32})', p.stdout)
        self.assertEqual(''.join(parts), hashlib.sha256(self.tree).hexdigest())
        self.assertIn('3.0 reference DTB: DIFFERENT', p.stdout)
        self.assertIn('No partition was written.', p.stdout)
        self.assert_read_only(before)

    def test_zip_extraction_path_and_corrupt_zip_failure(self):
        before = sha(self.boot)
        bundle = self.t / 'fixture.zip'
        # Fixture BusyBox wrapper exposes only the fake blockdev; all other
        # applets are the same host/ARM BusyBox used by this test class.
        with zipfile.ZipFile(bundle, 'w') as z:
            z.writestr('tools/busybox', (self.bin / 'busybox').read_bytes())
        p = self.audit(bundle=bundle)
        self.assertEqual(p.returncode, 0, p.stdout)
        parts = re.findall(r'DTB SHA256 [12]/2: ([0-9a-f]{32})', p.stdout)
        self.assertEqual(''.join(parts), hashlib.sha256(self.tree).hexdigest())
        self.assert_read_only(before)
        bundle.write_bytes(b'not a zip')
        p = self.audit(bundle=bundle)
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Cannot extract the bundled BusyBox', p.stdout)
        self.assertNotIn('DTB SHA256 1/2:', p.stdout)
        self.assert_read_only(before)

    def test_hash_covers_concatenated_and_trailing_dtb_bytes(self):
        self.make_boot(tree=fixture.fdt() + fixture.fdt(b'second\0') + b'padding')
        before = sha(self.boot)
        p = self.audit()
        self.assertEqual(p.returncode, 0, p.stdout)
        parts = re.findall(r'DTB SHA256 [12]/2: ([0-9a-f]{32})', p.stdout)
        self.assertEqual(''.join(parts), hashlib.sha256(self.tree).hexdigest())
        self.assert_read_only(before)

    def test_unsupported_or_malformed_headers_stop_without_hash(self):
        cases = ((0, b'NOTBOOT!', 'Not an Android boot image'),
                 (40, struct.pack('<I', 3), 'Only boot-v2'),
                 (36, struct.pack('<I', 2048), 'Only boot-v2'),
                 (1644, struct.pack('<I', 1661), 'Only boot-v2'),
                 (8, b'\xff' * 4, 'Invalid kernel size'),
                 (16, b'\0' * 4, 'Kernel or ramdisk section is empty'),
                 (1636, b'\0' * 4, 'Unexpected recovery DTBO offset'),
                 (1640, struct.pack('<I', 1), 'Recovery DTBO offset exceeds audit limit'),
                 (1648, struct.pack('<I', 0), 'DTB missing or exceeds audit limit'),
                 (1648, struct.pack('<I', 17 * 1024 * 1024), 'DTB missing or exceeds audit limit'),
                 (8, struct.pack('<I', 16 * 1024 * 1024), 'Boot sections exceed partition size'))
        for offset, value, message in cases:
            with self.subTest(message=message):
                self.make_boot()
                with self.boot.open('r+b') as f:
                    f.seek(offset)
                    f.write(value)
                before = sha(self.boot)
                p = self.audit()
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn(message, p.stdout)
                self.assertNotIn('DTB SHA256 1/2:', p.stdout)
                self.assert_read_only(before)

    def test_short_read_never_reports_a_hash(self):
        before = sha(self.boot)
        p = self.audit(SHORT_DTB='1')
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Short DTB read; no hash reported', p.stdout)
        self.assertNotIn('DTB SHA256 1/2:', p.stdout)
        self.assert_read_only(before)

    def test_ab_properties_and_partition_names_fail_closed(self):
        before = sha(self.boot)
        for env in ({'PROP_SUFFIX': '_a'}, {'PROP_SLOT': 'b'}, {'PROP_AB': 'true'},
                    {'PROP_AB': 'unexpected'}):
            with self.subTest(env=env):
                p = self.audit(**env)
                self.assertNotEqual(p.returncode, 0, p.stdout)
                self.assertIn('no boot selected', p.stdout)
                self.assertNotIn('DTB SHA256 1/2:', p.stdout)
                self.assert_read_only(before)
        self.cmdline.write_text('quiet androidboot.slot=a\n')
        p = self.audit()
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('A/B slot in kernel command line', p.stdout)
        self.assert_read_only(before)
        self.cmdline.write_text('quiet\n')
        (self.other / 'boot_a').symlink_to('does-not-exist')
        p = self.audit()
        self.assertNotEqual(p.returncode, 0, p.stdout)
        self.assertIn('Slotted boot names found', p.stdout)
        self.assert_read_only(before)

    def test_recovery_values_are_not_misrepresented_as_rom_or_hw_proof(self):
        before = sha(self.boot)
        p = self.audit(PROP_DEVICE='unknown with space')
        self.assertEqual(p.returncode, 0, p.stdout)
        self.assertIn('ro.product.device: (unexpected characters)', p.stdout)
        self.assertIn('Recovery properties can differ from the installed ROM.', p.stdout)
        self.assertIn('not proof of AVB trust, module ABI or boot safety', p.stdout)
        self.assert_read_only(before)


class PackageTests(unittest.TestCase):
    def setUp(self):
        original = os.environ.get('S3_COMPAT_ORIGINAL')
        if not original:
            self.skipTest('S3_COMPAT_ORIGINAL must point to the pinned original ZIP')
        self.original = Path(original)
        self.files = pkg.original_files(self.original)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.t = Path(self.temp.name)

    def test_outputs_are_reproducible_and_preserve_image_and_preparation(self):
        audit_files, compat = pkg.audit_files(self.files), pkg.compat_files(self.files)
        a, b = self.t / 'audit-a.zip', self.t / 'audit-b.zip'
        c, d = self.t / 'compat-a.zip', self.t / 'compat-b.zip'
        for path in (a, b):
            pkg.package(audit_files, path, {pkg.BINARY, 'boot-audit.sh', 'tools/busybox'})
        for path in (c, d):
            pkg.package(compat, path, {pkg.BINARY, 'anykernel.sh', 'tools/busybox',
                                       'tools/magiskboot', 'tools/prepare-boot.sh'})
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(c.read_bytes(), d.read_bytes())
        self.assertEqual({name for name in compat if compat[name] != self.files[name]},
                         {'anykernel.sh', pkg.BINARY, 'BUILD-INFO.json', 'README-FLASH.txt'})
        self.assertEqual(pkg.sha(compat['Image.gz']), pkg.IMAGE_SHA256)
        self.assertEqual(compat['tools/prepare-boot.sh'], self.files['tools/prepare-boot.sh'])
        self.assertEqual(compat['tools/magiskboot'], self.files['tools/magiskboot'])
        self.assertEqual(compat['tools/busybox'], self.files['tools/busybox'])
        self.assertEqual(compat['anykernel.sh'].count(pkg.REFERENCE_DTB.encode()), 1)
        self.assertNotIn('Image.gz', audit_files)
        self.assertNotIn('tools/magiskboot', audit_files)
        meta = json.loads(compat['BUILD-INFO.json'])
        self.assertEqual(meta['reference_dtb_sha256'], pkg.REFERENCE_DTB)
        self.assertEqual(meta['physical_boot_test_this_installer'], 'NOT RUN')
        self.assertIn(b'JANGAN FLASH', compat['README-FLASH.txt'])
        self.assertIn(b'TIDAK memasang atau menulis partisi', audit_files['README-ID.txt'])
        for name, content in ((pkg.BINARY, audit_files[pkg.BINARY]),
                              ('anykernel.sh', compat['anykernel.sh']), (pkg.BINARY, compat[pkg.BINARY])):
            path = self.t / 'syntax.sh'
            path.write_bytes(content)
            subprocess.run(['sh', '-n', str(path)], check=True)
            if shutil.which('busybox'):
                subprocess.run(['busybox', 'ash', '-n', str(path)], check=True)

    def test_exact_20_and_30_share_tools_but_have_known_config_differences(self):
        release = (ROOT / 'release/Synthetica-2.0.zip').read_bytes()
        self.assertEqual(hashlib.sha256(release).hexdigest(), previous.pkg.base.BASE_SHA256)
        with zipfile.ZipFile(io.BytesIO(release)) as z:
            self.assertEqual(z.read('tools/busybox'), self.files['tools/busybox'])
            self.assertEqual(z.read('tools/magiskboot'), self.files['tools/magiskboot'])
        baseline = (ROOT / 'artifacts/generated.config.txt').read_bytes()
        self.assertEqual(hashlib.sha256(baseline).hexdigest(), config_guard.V2_CONFIG_SHA256)
        actual = config_in_pinned_image(self.files['Image.gz'])
        info = json.loads(self.files['BUILD-INFO.json'])
        self.assertEqual(hashlib.sha256(actual).hexdigest(), info['config_sha256'])
        before, after = config_guard.read_config(baseline.decode()), config_guard.read_config(actual.decode())
        changes = {key: (before.get(key, 'n'), after.get(key, 'n'))
                   for key in set(before) | set(after)
                   if before.get(key, 'n') != after.get(key, 'n')}
        self.assertEqual(changes, {
            'LOCALVERSION': ('"-Synthetica-2.0"', '"-synthetica-3.0"'),
            'LRU_GEN': ('n', 'y'), 'LRU_GEN_ENABLED': ('n', 'y'),
            'NR_LRU_GENS': ('n', '7'), 'TIERS_PER_GEN': ('n', '4'),
            'UCLAMP_BUCKETS_COUNT': ('n', '5'), 'UCLAMP_TASK': ('n', 'y'),
            'UCLAMP_TASK_GROUP': ('n', 'y'),
        })

    def test_existing_output_and_tampered_original_are_rejected(self):
        with self.assertRaises(ValueError):
            pkg.package(pkg.audit_files(self.files), self.original, set())
        tampered = self.t / 'bad.zip'
        data = bytearray(self.original.read_bytes())
        data[len(data) // 2] ^= 1
        tampered.write_bytes(data)
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            pkg.original_files(tampered)

    def test_backend_does_not_mount_and_keeps_device_checks(self):
        backend = pkg.compat_backend(self.files[pkg.BINARY]).decode()
        bottom = backend[backend.rindex('\nshow_progress 1.0 0;'):]
        self.assertNotIn('\nsetup_env;', bottom)
        self.assertNotIn('\nrestore_env;', bottom)
        abort = backend[backend.index('\nabort() {'):backend.index('\ndo_devicecheck() {')]
        self.assertNotIn('\n  restore_env;', abort)
        for item in ('do_devicecheck;', 'do_versioncheck;', 'do_levelcheck;',
                     'do_vendorlevelcheck;', 'ash anykernel.sh;', 'if [ $? != 0 ]; then\n  abort;'):
            self.assertIn(item, bottom)

    @unittest.skipUnless(shutil.which('busybox') and shutil.which('unzip'), 'host BusyBox and unzip required')
    def test_backend_does_not_enter_mount_setup_on_success_or_abort(self):
        # Instrument only setup/restore functions; execute the actual backend
        # control flow with a disposable ZIP, harmless writer and host BusyBox.
        backend = pkg.compat_backend(self.files[pkg.BINARY]).decode()
        start, end = backend.index('setup_env() {'), backend.index('\nrestore_env() {')
        backend = backend[:start] + 'setup_env() { echo setup >> "$MARKER"; }\n' + backend[end:]
        start, end = backend.index('restore_env() {'), backend.index('\nsetup_bb() {')
        backend = backend[:start] + 'restore_env() { echo restore >> "$MARKER"; }\n' + backend[end:]
        update = self.t / 'update-binary'
        update.write_text(backend)
        fakebin = self.t / 'fakebin'
        fakebin.mkdir()
        getprop = fakebin / 'getprop'
        getprop.write_text('#!/bin/sh\n[ "$1" = ro.product.device ] && echo "${DEVICE-unrelated}"\nexit 0\n')
        getprop.chmod(0o755)
        busy = Path(shutil.which('busybox')).read_bytes()
        mockentry = '''properties() { '\nkernel.string=fixture\ndo.devicecheck=1\ndo.modules=0\ndo.systemless=0\ndo.cleanup=1\ndo.cleanuponabort=1\ndevice.name1=joyeuse\nsupported.versions=\nsupported.patchlevels=\nsupported.vendorpatchlevels=\n'; }\nexit "${FAKE_EXIT-0}"\n'''
        bundle = self.t / 'backend-fixture.zip'
        with zipfile.ZipFile(bundle, 'w') as z:
            z.writestr('tools/busybox', busy)
            z.writestr('anykernel.sh', mockentry)
        marker = self.t / 'mount-functions-called'
        for env, should_pass in (({'DEVICE': 'joyeuse'}, True),
                                 ({'DEVICE': 'unrelated'}, False),
                                 ({'DEVICE': 'joyeuse', 'FAKE_EXIT': '1'}, False)):
            with self.subTest(env=env):
                home = self.t / 'ak-home'
                p = subprocess.run(['busybox', 'ash', str(update), '3', '1', str(bundle)],
                                   env=os.environ | {'PATH': str(fakebin) + ':/usr/bin:/bin',
                                                     'AKHOME': str(home), 'MARKER': str(marker)} | env,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=20)
                self.assertEqual(p.returncode == 0, should_pass, p.stdout)
                self.assertFalse(marker.exists(), 'mount/environment setup or restore was invoked')
                self.assertFalse(home.exists(), 'temporary AnyKernel workspace was not cleaned')

    @unittest.skipUnless(shutil.which('busybox'), 'host BusyBox required')
    def test_actual_anykernel_devicecheck_for_all_five_names(self):
        backend = pkg.compat_backend(self.files[pkg.BINARY]).decode()
        function = backend[backend.index('do_devicecheck() {'):backend.index('\nint2ver() {')]
        (self.t / 'anykernel.sh').write_bytes(pkg.compat_entry(self.files['anykernel.sh']))
        getprop = self.t / 'getprop'
        getprop.write_text('''#!/bin/sh
case "$1" in
  ro.product.device) echo "${DEV-}";;
  ro.build.product) echo "${PRODUCT-}";;
  ro.product.vendor.device) echo "${VENDOR_DEVICE-}";;
  ro.vendor.product.device) echo "${VENDOR_PRODUCT-}";;
esac
''')
        getprop.chmod(0o755)
        harness = self.t / 'check.sh'
        harness.write_text('''file_getprop() { grep "^$2=" "$1" | tail -n1 | cut -d= -f2-; }
ui_print() { :; }
abort() { echo "REJECT"; exit 1; }
''' + function + '\ndo_devicecheck\necho MATCH\n')
        for env, expected in (({'DEV': 'joyeuse'}, True), ({'DEV': 'curtana'}, True),
                              ({'PRODUCT': 'excalibur'}, True), ({'VENDOR_DEVICE': 'gram'}, True),
                              ({'VENDOR_PRODUCT': 'miatoll'}, True), ({'DEV': 'unrelated'}, False),
                              ({}, False)):
            with self.subTest(env=env):
                p = subprocess.run(['busybox', 'ash', str(harness)], cwd=self.t,
                                   env=os.environ | {'PATH': str(self.t) + ':/usr/bin:/bin'} | env,
                                   text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=10)
                self.assertEqual(p.returncode == 0, expected, p.stdout)
                self.assertIn('MATCH' if expected else 'REJECT', p.stdout)


if __name__ == '__main__':
    unittest.main()
