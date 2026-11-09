"""Guards for the unsigned Manager UAPI-5 source prototype, not runtime tests."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import prepare_s40_manager_uapi5 as migration
import verify_s40_manager_uapi5_apk as apk_check


def fake_arm64_elf() -> bytes:
    header = bytearray(64)
    header[:6] = b'\x7fELF\x02\x01'
    struct.pack_into('<HH', header, 16, 3, 183)
    return bytes(header) + b'test-only fake daemon; not executable'


def pin_for(data: bytes) -> dict:
    return {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def tree_hashes(root: Path) -> dict[str, str]:
    return {
        p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in root.rglob('*') if p.is_file() and not p.is_symlink()
    }


class ArtifactGuardTests(unittest.TestCase):
    def test_daemon_requires_pinned_bytes_and_arm64_elf(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            daemon = base / 'ksud'
            data = fake_arm64_elf()
            daemon.write_bytes(data)
            with mock.patch.dict(migration.PINS['ksud_arm64'], pin_for(data)):
                migration.verify_daemon(daemon)
                daemon.write_bytes(data[:-1] + b'!')
                with self.assertRaisesRegex(ValueError, 'SHA-256'):
                    migration.verify_daemon(daemon)
                daemon.write_bytes(data + b'x')
                with self.assertRaisesRegex(ValueError, 'Unexpected'):
                    migration.verify_daemon(daemon)
                daemon.write_bytes(data)
                (base / 'link').symlink_to(daemon)
                with self.assertRaisesRegex(ValueError, 'symlink'):
                    migration.verify_daemon(base / 'link')
            bad = bytearray(data)
            struct.pack_into('<H', bad, 18, 62)  # x86-64
            daemon.write_bytes(bad)
            with mock.patch.dict(migration.PINS['ksud_arm64'], pin_for(bytes(bad))):
                with self.assertRaisesRegex(ValueError, 'arm64 ELF'):
                    migration.verify_daemon(daemon)

    def test_archive_mismatch_fails_before_preparation(self):
        with tempfile.TemporaryDirectory() as temp:
            archive = Path(temp) / 'wrong.tar.gz'
            archive.write_bytes(b'not the pinned archive')
            for name in ('old_manager', 'new_backend'):
                with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'SHA-256'):
                    migration.verify_archive(name, archive)


class PrototypeApkChecks(unittest.TestCase):
    @staticmethod
    def write_apk(path: Path, daemon: bytes, jni: bytes, extras: dict[str, bytes] | None = None):
        with zipfile.ZipFile(path, 'w') as apk:
            apk.writestr('lib/arm64-v8a/libksud.so', daemon)
            apk.writestr('lib/arm64-v8a/libkernelsu.so', jni)
            for name, data in (extras or {}).items():
                apk.writestr(name, data)

    def test_static_prototype_checks_and_tampered_daemon(self):
        daemon = fake_arm64_elf()
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(migration.PINS['ksud_arm64'], pin_for(daemon)):
            path = Path(temp) / 'fixture.zip'
            self.write_apk(path, daemon, fake_arm64_elf())
            result = apk_check.verify(path)
            self.assertFalse(result['runtime_tested'])
            self.assertFalse(result['signed'])
            self.assertFalse(result['installable_release'])
            self.write_apk(path, daemon[:-1] + b'!', fake_arm64_elf())
            with self.assertRaisesRegex(ValueError, 'ksud identity'):
                apk_check.verify(path)

    def test_other_abi_and_v1_signature_fail_closed(self):
        daemon = fake_arm64_elf()
        with tempfile.TemporaryDirectory() as temp, mock.patch.dict(migration.PINS['ksud_arm64'], pin_for(daemon)):
            path = Path(temp) / 'fixture.zip'
            for extras, error in (({'lib/x86_64/libother.so': b'x'}, 'native ABI'),
                                  ({'META-INF/CERT.RSA': b'x'}, 'v1 APK signature')):
                with self.subTest(extras=extras):
                    self.write_apk(path, daemon, fake_arm64_elf(), extras)
                    with self.assertRaisesRegex(ValueError, error):
                        apk_check.verify(path)


class ActualSourceMigrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old, new = os.environ.get('S40_MANAGER_OLD'), os.environ.get('S40_MANAGER_NEW')
        if not old or not new:
            raise unittest.SkipTest('set S40_MANAGER_OLD and S40_MANAGER_NEW to pinned source trees')
        cls.old, cls.new = Path(old), Path(new)
        migration.verify_source('old_manager', cls.old)
        migration.verify_source('new_backend', cls.new)

    def test_delta_and_prepared_tree_preserve_all_but_allowlisted_files(self):
        data = fake_arm64_elf()
        with tempfile.TemporaryDirectory(prefix='s40-manager-test-') as temp:
            base = Path(temp)
            daemon = base / 'fake-ksud'
            daemon.write_bytes(data)
            baseline = base / 'baseline'
            shutil.copytree(self.old, baseline, symlinks=True)
            migration.base501.prepare_tree(baseline)
            with mock.patch.dict(migration.PINS['ksud_arm64'], pin_for(data)):
                source = migration.prepare(self.old, self.new, daemon, base / 'work')
            old_hashes, new_hashes = tree_hashes(baseline), tree_hashes(source)
            self.assertEqual(old_hashes.keys(), new_hashes.keys())
            changed = {name for name in old_hashes if old_hashes[name] != new_hashes[name]}
            self.assertEqual(changed, {
                'uapi/supercall.h', 'uapi/feature.h',
                'manager/build.gradle.kts', 'manager/app/build.gradle.kts',
                'manager/app/src/main/cpp/ksu.cc',
                'manager/app/src/main/jniLibs/arm64-v8a/libksud.so',
                'manager/app/src/main/res/values/strings_synthetica.xml',
                'manager/app/src/main/res/values-in-rID/strings_synthetica.xml',
            })
            self.assertTrue((source / 'manager/app/src/main/cpp/uapi').is_symlink())
            self.assertEqual((source / 'manager/app/src/main/cpp/uapi').resolve(), (source / 'uapi').resolve())
            self.assertIn('KERNEL_SU_UAPI_VERSION = 5;', (source / 'uapi/supercall.h').read_text())
            self.assertIn('kernelUAPIVersion == managerUAPIVersion',
                          (source / 'manager/app/src/main/java/com/rifsxd/ksunext/Natives.kt').read_text())
            self.assertIn('applicationId = "net.ember.labs"', (source / 'manager/app/build.gradle.kts').read_text())
            self.assertIn('5.0.1-uapi5-dev', (source / 'manager/build.gradle.kts').read_text())
            report = json.loads((base / 'work/PROTOTYPE.json').read_text())
            self.assertFalse(report['signed'])
            self.assertFalse(report['installable_release'])
            self.assertFalse(report['runtime_tested'])
            self.assertFalse(report['kernel_apk_v3_blocker_resolved'])
            migration.verify_source('old_manager', self.old)  # original source remains unchanged

    def test_rejects_an_unexpected_third_uapi_header_change(self):
        with tempfile.TemporaryDirectory(prefix='s40-uapi-delta-') as temp:
            new = Path(temp) / 'new'
            shutil.copytree(self.new, new, symlinks=True)
            with (new / 'uapi/ksu.h').open('a') as f:
                f.write('\n/* unexpected drift */\n')
            with self.assertRaisesRegex(ValueError, 'Unexpected UAPI header differences'):
                migration.verify_uapi_delta(self.old, new)

    @unittest.skipUnless(shutil.which('g++'), 'g++ required')
    def test_actual_new_native_code_interprets_supported_bit(self):
        cpp = (self.new / 'manager/app/src/main/cpp/ksu.cc').read_text()
        start = cpp.index('bool is_su_enabled() {')
        end = cpp.index('static inline bool set_feature(', start)
        actual = cpp[start:end]
        preamble = r'''
#include <cstdint>
struct ksu_get_feature_cmd { uint32_t feature_id; uint64_t value; uint8_t supported; };
constexpr int KSU_IOCTL_GET_FEATURE = 1;
constexpr int KSU_FEATURE_SU_COMPAT = 0;
constexpr int KSU_FEATURE_FLAG_SUPPORTED = 1;
static uint8_t flags;
static uint64_t value;
static int result;
static int ksuctl(int op, ksu_get_feature_cmd *cmd) {
    (void)op; cmd->value = value; cmd->supported = flags; return result;
}
'''
        harness = r'''
int main() {
    for (int bits = 0; bits != 4; ++bits) {
        flags = bits; value = 1; result = 0;
        bool supported = false; uint64_t out = 0;
        if (is_su_enabled() != bool(bits & 1)) return 1;
        if (!get_feature(42, &out, &supported) || supported != bool(bits & 1) || out != 1) return 2;
        value = 0;
        if (is_su_enabled()) return 3;
    }
    result = -1;
    if (is_su_enabled() || get_feature(42, nullptr, nullptr)) return 4;
    return 0;
}
'''
        with tempfile.TemporaryDirectory(prefix='s40-native-flags-') as temp:
            src = Path(temp) / 'flags.cc'
            exe = Path(temp) / 'flags'
            src.write_text(preamble + actual + harness)
            subprocess.run(['g++', '-std=c++17', '-Wall', '-Wextra', '-Werror', str(src), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
