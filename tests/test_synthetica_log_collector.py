"""Exercise the diagnostic-only collector on isolated fake recovery filesystems."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tarfile
import tempfile
import threading
import time
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'build-kit/ci/log-collector/collector.sh'
README = ROOT / 'build-kit/ci/log-collector/README-ID.txt'
PACKAGER = ROOT / 'build-kit/scripts/package_log_collector.py'
spec = importlib.util.spec_from_file_location('collector_package', PACKAGER)
assert spec and spec.loader
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class RecoveryFixture:
    def __init__(self, base: Path):
        self.base = base
        for d in ('proc', 'tmp', 'bin', 'data/media/0', 'sys/fs/pstore',
                  'dev/block/bootdevice/by-name', 'system'):
            (base / d).mkdir(parents=True, exist_ok=True)
        (base / '.synthetica-collector-fixture').touch()
        (base / 'sdcard').symlink_to(base / 'data/media/0', target_is_directory=True)
        self.write('proc/mounts', f'/dev/fake {base}/data ext4 rw 0 0\n'
                   f'/dev/fake-system {base}/system ext4 ro 0 0\n'
                   f'tmpfs {base}/tmp tmpfs rw 0 0\n')
        self.write('proc/cmdline', 'androidboot.slot_suffix=_a androidboot.hardware=qcom '
                   'androidboot.serialno=DO_NOT_COPY serial=DO_NOT_COPY\n')
        self.write('proc/last_kmsg', 'PREVIOUS synthetic kernel panic\n')
        self.write('tmp/recovery.log', 'Installing kernel\nPREPARE FAILED: boot DTB differs\nError 1\n')
        self.write('sys/fs/pstore/dmesg-ramoops-0', 'Synthetic pstore kernel panic\n')
        self.write('system/build.prop', 'ro.build.version.release=15\nro.build.version.sdk=35\n'
                   'ro.serialno=DO_NOT_COPY\n')
        self.command('getprop', '''case "$1" in
ro.product.device) echo example ;;
ro.build.version.release) echo 14 ;;
ro.boot.slot_suffix) echo _a ;;
ro.serialno) echo DO_NOT_COPY ;;
esac''')
        self.command('dmesg', 'echo synthetic-recovery-dmesg')
        self.command('logcat', 'echo synthetic-recovery-logcat')
        # If any unexpected mutating command is invoked, create an observable marker.
        for cmd in ('mount', 'umount', 'reboot', 'setprop', 'fastboot', 'su', 'flash_image'):
            self.command(cmd, 'echo called >> "$SYNT_COLLECTOR_TEST_ROOT/unsafe-called"\nexit 87')

    def write(self, path: str, contents: str | bytes) -> Path:
        file = self.base / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(contents.encode() if isinstance(contents, str) else contents)
        return file

    def command(self, name: str, body: str) -> None:
        # /bin/sh is available for host tests. Android emulator has separate stubs.
        f = self.write('bin/' + name, '#!/bin/sh\n' + body + '\n')
        f.chmod(0o755)

    def boot(self, name: str = 'boot', *, version: int = 2, magic: bytes = b'ANDROID!') -> Path:
        data = bytearray(4096)
        data[:8] = magic
        struct.pack_into('<I', data, 8, 123456)
        struct.pack_into('<I', data, 12, 65432)
        struct.pack_into('<I', data, 36, 4096)
        struct.pack_into('<I', data, 40, version)
        struct.pack_into('<I', data, 1644, 1660)
        data[500:520] = b'DO_NOT_COPY_SERIAL!!'
        return self.write('dev/block/bootdevice/by-name/' + name, bytes(data))

    def run(self, *, shell: str = 'sh', args: tuple[str, ...] = (), timeout: int = 25,
            extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, 'SYNT_COLLECTOR_TEST_ROOT': str(self.base), **(extra_env or {})}
        command = [shell, str(SCRIPT), *args]
        if shell == 'busybox':
            command.insert(1, 'ash')
        return subprocess.run(command, text=True, capture_output=True, env=env, timeout=timeout)

    @staticmethod
    def report(result: subprocess.CompletedProcess[str]) -> Path:
        if result.returncode != 0:
            raise AssertionError(f'collector failed: {result.returncode}\n{result.stdout}\n{result.stderr}')
        match = re.search(r'^(?:ui_print )?Report folder: (.+)$', result.stdout, re.MULTILINE)
        if not match:
            raise AssertionError(f'no output path in {result.stdout!r}')
        return Path(match.group(1).strip())


class CollectorFilesystemTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetica-log-fixture-')
        self.addCleanup(self.tmp.cleanup)
        self.fixture = RecoveryFixture(Path(self.tmp.name))

    def test_real_script_collects_failure_crash_and_readonly_metadata(self):
        f = self.fixture
        boot = f.boot()
        before = hashlib.sha256(boot.read_bytes()).hexdigest()
        f.write('tmp/anykernel/prepare.log', 'PREPARE FAILED: boot DTB is not the known reference\n')
        f.write('cache/recovery/last_log', 'previous recovery log\n')
        f.write('data/media/0/Synthetica/install-log-20261107.txt', 'legacy install output\n')
        for shell in ('sh', 'busybox'):
            if shell == 'busybox' and not shutil.which('busybox'):
                continue
            with self.subTest(shell=shell):
                result = f.run(shell=shell)
                report = f.report(result)
                self.assertTrue(report.resolve().is_relative_to((f.base / 'data/media/0').resolve()))
                self.assertIn('Error 1', (report / '01-recovery-current.log').read_text())
                self.assertIn('DTB', (report / '03-anykernel-prepare.log').read_text())
                self.assertIn('panic', (report / '09-proc-last-kmsg.log').read_text())
                self.assertIn('panic', (report / 'pstore-dmesg-ramoops-0.log').read_text())
                self.assertIn('legacy install', (report / 'installer-log-1.txt').read_text())
                self.assertIn('synthetic-recovery-dmesg', (report / '10-dmesg-recovery.log').read_text())
                self.assertIn('synthetic-recovery-logcat', (report / '11-logcat-recovery.log').read_text())
                context = (report / '12-recovery-context.txt').read_text()
                self.assertIn('ro.build.version.release=14', context)
                self.assertIn('ro.boot.slot_suffix=_a', context)
                self.assertIn('androidboot.hardware=qcom', context)
                self.assertNotIn('DO_NOT_COPY', context)
                rom = (report / '13-mounted-rom-properties.txt').read_text()
                self.assertIn('ro.build.version.release=15', rom)
                self.assertNotIn('DO_NOT_COPY', rom)
                layout = (report / '14-partition-layout.txt').read_text()
                for text in ('header_version=2', 'legacy_page_bytes=4096', 'legacy_header_bytes=1660'):
                    self.assertIn(text, layout)
                self.assertNotIn('DO_NOT_COPY_SERIAL', layout)
                self.assertIn('PREPARE FAILED', (report / '15-error-lines.txt').read_text())
                statuses = (report / 'STATUS.tsv').read_text()
                self.assertIn('report\tCOMPLETE', statuses)
                self.assertIn('06-last-install-cache.txt\tMISSING', statuses)
                self.assertIn('recovery-properties\tOK', statuses)
                self.assertFalse((f.base / 'unsafe-called').exists())
                self.assertEqual(hashlib.sha256(boot.read_bytes()).hexdigest(), before)
                archive = Path(str(report) + '.tar.gz')
                self.assertTrue(archive.is_file(), result.stdout)
                with tarfile.open(archive, 'r:gz') as tar:
                    members = tar.getmembers()
                    self.assertTrue(members)
                    self.assertTrue(all(m.name == report.name or m.name.startswith(report.name + '/') for m in members))
                    self.assertFalse(any(m.issym() or m.islnk() for m in members))
                    content = tar.extractfile(report.name + '/01-recovery-current.log')
                    assert content is not None
                    self.assertIn(b'Error 1', content.read())

    def test_recovery_protocol_and_original_log_are_captured_before_first_ui(self):
        f = self.fixture
        read_fd, write_fd = os.pipe()
        messages: list[bytes] = []
        def receive() -> None:
            with os.fdopen(read_fd, 'rb', buffering=0) as stream:
                first = True
                while chunk := stream.read(4096):
                    messages.append(chunk)
                    if first:
                        with (f.base / 'tmp/recovery.log').open('a') as log:
                            log.write('COLLECTOR OPERATION STARTED\n')
                        first = False
        reader = threading.Thread(target=receive, daemon=True)
        reader.start()
        env = {**os.environ, 'SYNT_COLLECTOR_TEST_ROOT': str(f.base)}
        proc = subprocess.Popen(['sh', str(SCRIPT), '3', str(write_fd), '/unused/collector.zip'],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env,
                                pass_fds=(write_fd,), text=True)
        os.close(write_fd)
        stdout, stderr = proc.communicate(timeout=25)
        reader.join(timeout=5)
        self.assertEqual(proc.returncode, 0, stdout + stderr)
        transcript = b''.join(messages).decode()
        self.assertIn('ui_print Synthetica Log Collector', transcript)
        self.assertIn('ui_print Report folder:', transcript)
        match = re.search(r'^ui_print Report folder: (.+)$', transcript, re.MULTILINE)
        assert match is not None
        report = Path(match.group(1))
        self.assertNotIn('COLLECTOR OPERATION STARTED', (report / '01-recovery-current.log').read_text())
        self.assertIn('COLLECTOR OPERATION STARTED', (f.base / 'tmp/recovery.log').read_text())

    def test_unmounted_or_fake_sdcard_is_not_treated_as_persistent(self):
        f = self.fixture
        f.write('proc/mounts', f'tmpfs {f.base}/tmp tmpfs rw 0 0\n')
        result = f.run()
        report = f.report(result)
        self.assertTrue(report.is_relative_to(f.base / 'tmp'))
        self.assertIn('TEMPORARY /tmp', result.stdout)
        self.assertFalse((f.base / 'data/media/0/Synthetica-logs').exists())
        self.assertIn('13-mounted-rom-properties.txt\tUNAVAILABLE', (report / 'STATUS.tsv').read_text())

    def test_symlinked_logroot_and_pstore_entry_are_not_followed(self):
        f = self.fixture
        victim = f.base / 'victim'
        victim.mkdir()
        (victim / 'sentinel').write_text('unchanged')
        (f.base / 'data/media/0/Synthetica-logs').symlink_to(victim, target_is_directory=True)
        (f.base / 'sys/fs/pstore/evil').symlink_to(victim / 'sentinel')
        report = f.report(f.run())
        self.assertTrue(report.is_relative_to(f.base / 'tmp'))
        self.assertEqual((victim / 'sentinel').read_text(), 'unchanged')
        self.assertEqual([p.name for p in victim.iterdir()], ['sentinel'])
        self.assertIn('pstore-evil.log\tSKIPPED_SYMLINK', (report / 'STATUS.tsv').read_text())
        self.assertFalse((report / 'pstore-evil.log').exists())

    def test_missing_and_empty_sources_are_explicit_not_false_success(self):
        f = self.fixture
        (f.base / 'sys/fs/pstore/dmesg-ramoops-0').unlink()
        (f.base / 'proc/last_kmsg').unlink()
        f.write('tmp/recovery.log', '')
        f.write('proc/mounts', f'/dev/fake {f.base}/data ext4 rw 0 0\n')
        report = f.report(f.run())
        status = (report / 'STATUS.tsv').read_text()
        self.assertIn('01-recovery-current.log\tEMPTY', status)
        self.assertIn('09-proc-last-kmsg.log\tMISSING', status)
        self.assertIn('pstore\tUNAVAILABLE_OR_EMPTY', status)
        self.assertIn('13-mounted-rom-properties.txt\tUNAVAILABLE', status)
        self.assertIn('14-partition-layout.txt\tUNAVAILABLE', status)
        self.assertNotIn('ro.build.version.release=15', (report / '13-mounted-rom-properties.txt').read_text())

    def test_logs_are_bounded_and_privacy_warning_is_honest(self):
        f = self.fixture
        f.write('tmp/recovery.log', b'x' * (1048576 + 150) + b'\nError 1 at end SERIAL-PRIVATE\n')
        f.write('sys/fs/pstore/dmesg-ramoops-0', b'p' * (524288 + 15))
        report = f.report(f.run())
        recovery = (report / '01-recovery-current.log').read_bytes()
        self.assertEqual(len(recovery), 1048576)
        self.assertIn(b'Error 1 at end SERIAL-PRIVATE', recovery)
        self.assertEqual((report / 'pstore-dmesg-ramoops-0.log').stat().st_size, 524288)
        status = (report / 'STATUS.tsv').read_text()
        self.assertIn('01-recovery-current.log\tLIMIT_REACHED', status)
        self.assertIn('pstore-dmesg-ramoops-0.log\tLIMIT_REACHED', status)
        self.assertIn('PRIVASI', (report / 'README.txt').read_text())
        self.assertIn('TIDAK menjamin redaksi', (report / 'README.txt').read_text())

    def test_legacy_logs_prefer_last_five_sorted_names(self):
        f = self.fixture
        for n in range(1, 7):
            f.write(f'data/media/0/Synthetica/install-log-{n:04}.txt', f'example {n}\n')
        report = f.report(f.run())
        values = [(report / f'installer-log-{n}.txt').read_text().strip() for n in range(1, 6)]
        self.assertEqual(values, [f'example {n}' for n in range(2, 7)])
        self.assertFalse((report / 'installer-log-6.txt').exists())

    def test_boot_v2_v4_and_vendor_boot_metadata_no_raw_header(self):
        f = self.fixture
        a = f.boot('boot_a', version=2)
        b = f.boot('boot_b', version=4)
        v = f.boot('vendor_boot_a', version=4, magic=b'VNDRBOOT')
        before = [p.read_bytes() for p in (a, b, v)]
        report = f.report(f.run())
        layout = (report / '14-partition-layout.txt').read_text()
        self.assertIn('boot_a', layout)
        self.assertIn('header_version=2', layout)
        self.assertIn('header_version=4', layout)
        self.assertIn('page/header-size layout not interpreted', layout)
        self.assertIn('magic=VNDRBOOT', layout)
        self.assertNotIn('DO_NOT_COPY_SERIAL', layout)
        self.assertEqual(before, [p.read_bytes() for p in (a, b, v)])
        self.assertFalse(any(p.suffix in ('.img', '.bin') for p in report.iterdir()))

    def test_failed_and_timed_out_commands_are_reported(self):
        f = self.fixture
        f.command('dmesg', 'echo permission-denied >&2\nexit 42')
        f.command('logcat', 'exec sleep 30')
        started = time.monotonic()
        report = f.report(f.run(timeout=22))
        self.assertLess(time.monotonic() - started, 18)
        status = (report / 'STATUS.tsv').read_text()
        self.assertIn('10-dmesg-recovery.log\tCOMMAND_FAILED\texit=42', status)
        self.assertRegex(status, r'11-logcat-recovery.log\tTIMED_OUT\texit=(124|143)')
        self.assertIn('permission-denied', (report / '10-dmesg-recovery.log').read_text())

    def test_existing_archive_is_not_overwritten_or_deleted(self):
        f = self.fixture
        # Simulate a collision appearing when this new session directory is created.
        f.command('mkdir', '''/bin/mkdir "$@" || exit $?
case "$1" in */Synthetica-logs/*) echo sentinel > "$1.tar.gz" ;; esac''')
        result = f.run()
        report = f.report(result)
        archive = Path(str(report) + '.tar.gz')
        self.assertEqual(archive.read_text().strip(), 'sentinel')
        self.assertIn('already exists; it was not overwritten', result.stdout)

    def test_no_writable_destination_fails_without_mounting(self):
        f = self.fixture
        f.write('proc/mounts', '')
        shutil.rmtree(f.base / 'tmp')
        result = f.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('No writable log destination', result.stdout)
        self.assertFalse((f.base / 'unsafe-called').exists())

    def test_unmarked_fixture_override_is_refused(self):
        (self.fixture.base / '.synthetica-collector-fixture').unlink()
        result = self.fixture.run()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Invalid test fixture', result.stdout)

    def test_fixture_without_commands_never_falls_back_to_real_logs(self):
        f = self.fixture
        for name in ('dmesg', 'logcat', 'getprop'):
            (f.base / 'bin' / name).unlink()
        for shell in ('sh', 'busybox'):
            if shell == 'busybox' and not shutil.which('busybox'):
                continue
            report = f.report(f.run(shell=shell))
            statuses = (report / 'STATUS.tsv').read_text()
            self.assertIn('10-dmesg-recovery.log\tMISSING_COMMAND', statuses)
            self.assertIn('11-logcat-recovery.log\tMISSING_COMMAND', statuses)
            self.assertIn('recovery-properties\tMISSING_COMMAND', statuses)
            self.assertFalse((report / '10-dmesg-recovery.log').exists())
            self.assertFalse((report / '11-logcat-recovery.log').exists())


class CollectorPackageTests(unittest.TestCase):
    def test_zip_is_deterministic_small_and_contains_only_diagnostic_files(self):
        with tempfile.TemporaryDirectory(prefix='collector-package-test-') as d:
            one = Path(d) / 'one.zip'
            two = Path(d) / 'two.zip'
            info = package.package(one)
            package.package(two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertLess(info['bytes'], 100000)
            with zipfile.ZipFile(one) as z:
                self.assertEqual(set(z.namelist()), package.EXPECTED_NAMES)
                self.assertEqual(z.read(package.BINARY), SCRIPT.read_bytes())
                self.assertEqual(z.read('collector.sh'), z.read(package.BINARY))
                self.assertEqual(z.read('README-ID.txt'), README.read_bytes())
                self.assertIsNone(z.testzip())
                self.assertFalse(any(n.lower().endswith(('.img', '.apk', '.so')) for n in z.namelist()))
            self.assertIn('not device-tested', str(package.verify(one)['kind']))
            with self.assertRaises(ValueError):
                package.package(one)
            self.assertEqual(one.read_bytes(), two.read_bytes())

    def test_tampered_zip_or_duplicate_entry_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix='collector-tamper-test-') as d:
            path = Path(d) / 'bad.zip'
            package.package(path)
            with zipfile.ZipFile(path, 'a') as z:
                z.writestr('Image.gz', b'not permitted')
            with self.assertRaises(ValueError):
                package.verify(path)

    def test_diagnostics_source_has_no_flash_mount_network_or_reboot_commands(self):
        script = SCRIPT.read_text()
        self.assertTrue(script.startswith('#!/sbin/sh\n'))
        self.assertNotRegex(script, r'(?m)^\s*(?:app\s+)?(?:mount|umount|reboot|setprop|fastboot|su|flash_image|curl|wget)\b')
        self.assertNotRegex(script, r'\bdd\s+[^\n]*\bof=/dev/')
        self.assertNotRegex(script, r'(?m)^\s*getprop\s*(?:>|$)')
        self.assertIn('pstore', script)
        self.assertIn('last_kmsg', script)
        self.assertIn('tail -c', script)

    def test_shell_syntax_on_available_host_shells(self):
        subprocess.run(['sh', '-n', str(SCRIPT)], check=True)
        if shutil.which('busybox'):
            subprocess.run(['busybox', 'ash', '-n', str(SCRIPT)], check=True)


if __name__ == '__main__':
    unittest.main()
