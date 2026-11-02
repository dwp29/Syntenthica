"""Host-only synthetic tests; no phone or actual ROM images are used."""
from __future__ import annotations

import hashlib
import io
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_checkvintf_snapshot as audit


class SnapshotPathTests(unittest.TestCase):
    def test_known_paths_map_to_correct_guest_partitions(self):
        cases = {
            ('system', '/system/etc/vintf/manifest.xml'): '/system/etc/vintf/manifest.xml',
            ('system', '/system/manifest.xml'): '/system/manifest.xml',
            ('vendor', '/etc/vintf/manifest/foo.xml'): '/vendor/etc/vintf/manifest/foo.xml',
            ('vendor', '/manifest.xml'): '/vendor/manifest.xml',
            ('vendor', '/odm/etc/vintf/manifest.xml'): '/odm/etc/vintf/manifest.xml',
            ('vendor', '/odm/etc/manifest.xml'): '/odm/etc/manifest.xml',
            ('system_ext', '/etc/vintf/x.xml'): '/system_ext/etc/vintf/x.xml',
            ('product', '/etc/vintf/x.xml'): '/product/etc/vintf/x.xml',
        }
        for (partition, path), expected in cases.items():
            with self.subTest(partition=partition, path=path):
                self.assertEqual(audit.guest_path(partition, path), expected)

    def test_unexpected_or_traversal_paths_are_refused(self):
        for partition, path in [('system', '/system/other.xml'), ('vendor', '/etc/vintf/../bad.xml'),
                                ('vendor', '/etc/vintf//x.xml'), ('vendor', 'etc/vintf/x.xml'),
                                ('vendor', '/odm/etc/not-vintf.xml'), ('odm', '/etc/vintf/x.xml'),
                                ('system', '/system/etc/vintf/raw.bin')]:
            with self.subTest(partition=partition, path=path), self.assertRaises(audit.CheckAuditError):
                audit.guest_path(partition, path)

    def test_copy_is_exact_and_duplicate_is_rejected(self):
        data = b'<manifest version="1.0" type="device"/>'
        with tempfile.TemporaryDirectory() as temp:
            snapshot = Path(temp)
            seen = {}
            audit.capture_snapshot(snapshot, seen, 'vendor', '/etc/vintf/manifest.xml', data)
            actual = snapshot / 'vendor/etc/vintf/manifest.xml'
            self.assertEqual(actual.read_bytes(), data)
            self.assertEqual(actual.stat().st_mode & 0o777, 0o444)
            self.assertEqual(seen['/vendor/etc/vintf/manifest.xml']['sha256'], hashlib.sha256(data).hexdigest())
            with self.assertRaises(audit.CheckAuditError):
                audit.capture_snapshot(snapshot, seen, 'vendor', '/etc/vintf/manifest.xml', data)

    def test_capture_rejects_bad_xml_and_symlink_parent(self):
        with tempfile.TemporaryDirectory() as temp, tempfile.TemporaryDirectory() as outside:
            root = Path(temp)
            with self.assertRaises(audit.inventory.VintfAuditError):
                audit.capture_snapshot(root, {}, 'vendor', '/etc/vintf/manifest.xml', b'<bad')
            (root / 'vendor').symlink_to(outside, target_is_directory=True)
            with self.assertRaises(audit.CheckAuditError):
                audit.capture_snapshot(root, {}, 'vendor', '/etc/vintf/manifest.xml', b'<manifest/>')
            self.assertEqual(list(Path(outside).iterdir()), [])


class ToolAndControlTests(unittest.TestCase):
    def test_unverified_archive_is_rejected_before_extraction(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'not-otatools.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('bin/checkvintf', b'not a tool')
            sandbox = root / 'sandbox'
            sandbox.mkdir()
            with self.assertRaises(audit.CheckAuditError):
                audit.prepare_tool(archive, sandbox)
            self.assertEqual(list(sandbox.iterdir()), [])

    @unittest.skipUnless(all((Path('/lib/x86_64-linux-gnu') / name).is_file() for name in audit.HOST_LIBS),
                         'Host system libraries required for this synthetic layout test')
    def test_tool_layout_marks_elf_interpreter_executable(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            archive = root / 'synthetic.zip'
            fake = b'synthetic executable bytes, never run'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('bin/checkvintf', fake)
            sandbox = root / 'sandbox'
            sandbox.mkdir()
            readelf = subprocess.CompletedProcess([], 0, stdout='\n'.join(
                f'  0x1 (NEEDED) Shared library: [{name}]' for name in audit.HOST_LIBS), stderr='')
            with mock.patch.object(audit, 'AOSP_ZIP_BYTES', archive.stat().st_size), \
                    mock.patch.object(audit, 'AOSP_ZIP_SHA256', hashlib.sha256(archive.read_bytes()).hexdigest()), \
                    mock.patch.object(audit, 'CHECKVINTF_SHA256', hashlib.sha256(fake).hexdigest()), \
                    mock.patch.object(audit.subprocess, 'run', return_value=readelf):
                audit.prepare_tool(archive, sandbox)
            self.assertEqual((sandbox / 'tool/checkvintf').stat().st_mode & 0o777, 0o555)
            self.assertEqual((sandbox / 'lib64/ld-linux-x86-64.so.2').stat().st_mode & 0o777, 0o555)
            self.assertEqual((sandbox / 'lib/x86_64-linux-gnu/libc.so.6').stat().st_mode & 0o777, 0o444)

    @unittest.skipUnless(shutil.which('unshare') and Path('/usr/bin/true').exists() and
                         (Path('/lib/x86_64-linux-gnu') / 'ld-linux-x86-64.so.2').is_file(),
                         'Namespace tooling and host ELF loader are required')
    def test_isolated_root_runs_only_a_synthetic_host_command(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'tool').mkdir()
            (root / 'lib/x86_64-linux-gnu').mkdir(parents=True)
            (root / 'lib64').mkdir()
            shutil.copy2('/usr/bin/true', root / 'tool/checkvintf')
            shutil.copyfile('/lib/x86_64-linux-gnu/libc.so.6', root / 'lib/x86_64-linux-gnu/libc.so.6')
            shutil.copyfile('/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', root / 'lib64/ld-linux-x86-64.so.2')
            (root / 'lib64/ld-linux-x86-64.so.2').chmod(0o555)
            (root / 'readonly-marker').write_text('synthetic')
            proc = subprocess.run(['unshare', '--user', '--map-root-user', '--mount', '--net', '--pid', '--fork',
                                   sys.executable, '-I', '-S', '-c', audit._ISOLATED_LAUNCHER, str(root)],
                                  capture_output=True, text=True, timeout=15)
            if proc.returncode and 'Operation not permitted' in proc.stderr:
                self.skipTest('User namespaces are disabled on this host')
            self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_build_args_explicitly_maps_all_and_does_not_assume_a_sku(self):
        args = audit.build_args('/snapshot', None)
        self.assertEqual(args[0], '--check-compat')
        self.assertEqual(args.count('--dirmap'), 6)
        self.assertNotIn('--kernel', args)
        self.assertNotIn('--property', args)
        self.assertIn('/odm:/snapshot/odm', args)
        self.assertIn('/apex:/snapshot/apex', args)
        api_args = audit.build_args('/snapshot', 30)
        self.assertEqual(api_args[-2:], ['--property', 'ro.product.first_api_level=30'])
        for bad_path, api in [('/outside', 30), ('/snapshot/..', None), ('/snapshot', True), ('/snapshot', 101)]:
            with self.subTest(path=bad_path, api=api), self.assertRaises(audit.CheckAuditError):
                audit.build_args(bad_path, api)

    def test_positive_negative_and_bad_synthetic_fixture_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            for scenario, version, malformed in [('pass', '0.0', False), ('fail', '1.0', False), ('bad', '0.0', True)]:
                audit.create_synthetic_fixture(base / scenario, version, malformed=malformed)
                self.assertTrue(all((base / scenario / name).is_dir() for name in audit.MAPPINGS))
            good_matrix = (base / 'pass/system/etc/vintf/compatibility_matrix.1.xml').read_text()
            bad_matrix = (base / 'fail/system/etc/vintf/compatibility_matrix.1.xml').read_text()
            self.assertIn('<sepolicy-version>0.0</sepolicy-version>', good_matrix)
            self.assertIn('<sepolicy-version>1.0</sepolicy-version>', bad_matrix)
            self.assertEqual((base / 'bad/vendor/etc/vintf/manifest.xml').read_text(), '<manifest')

    def test_exit_categories_do_not_confuse_errors_or_incompatibility(self):
        cases = [(0, b'COMPATIBLE\n', 'compatible_for_supplied_snapshot'),
                 (65, b'INCOMPATIBLE\n', 'incompatible_for_supplied_snapshot'),
                 (70, b'', 'tool_error_or_incomplete_input'),
                 (0, b'INCOMPATIBLE\n', 'tool_error_or_incomplete_input'),
                 (65, b'COMPATIBLE\n', 'tool_error_or_incomplete_input')]
        for code, output, expected in cases:
            proc = mock.Mock(returncode=code)
            proc.communicate.return_value = (output, b'Cannot find framework matrix at FCM version 4\n')
            with self.subTest(code=code, output=output), \
                    mock.patch.object(audit.shutil, 'which', return_value='/usr/bin/unshare'), \
                    mock.patch.object(audit.subprocess, 'Popen', return_value=proc):
                result, raw = audit.run_isolated(Path('/tmp/synthetic-root'), '/snapshot', None)
                self.assertEqual(result['tool_result'], expected)
                self.assertTrue(result['diagnostic_markers']['missing_exact_target_fcm_matrix'])
                self.assertNotIn('Cannot find framework', str(result))
                self.assertIn('Cannot find framework', raw)

    def test_controls_stop_before_real_input_if_expected_result_differs(self):
        fake = {'tool_result': 'tool_error_or_incomplete_input', 'exit_code': 70}
        with tempfile.TemporaryDirectory() as temp, \
                mock.patch.object(audit, 'run_isolated', return_value=(fake, 'synthetic failure')):
            with self.assertRaisesRegex(audit.CheckAuditError, 'Synthetic pass expected'):
                audit.run_controls(Path(temp))


@unittest.skipUnless(audit.inventory.pytsk3 and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(),
                     'Synthetic ext4 integration needs pytsk3 and e2fsprogs')
class LegacyExt4Tests(unittest.TestCase):
    def test_legacy_files_are_captured_without_changing_extent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / 'synthetic.img'
            with image.open('wb') as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', str(image)],
                           check=True, capture_output=True)
            xml = root / 'legacy.xml'
            xml.write_bytes(b'<manifest version="1.0" type="device"/>')
            subprocess.run(['/usr/sbin/debugfs', '-w', '-R', f'write {xml} /manifest.xml', str(image)],
                           check=True, capture_output=True)
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            captured, rows = [], []
            audit.scan_legacy(image, 'vendor', lambda *row: captured.append(row), rows)
            self.assertEqual(captured, [('vendor', '/manifest.xml', xml.read_bytes())])
            self.assertEqual(rows[0]['status'], 'read')
            self.assertEqual(rows[1]['status'], 'missing_or_unreadable')
            self.assertEqual(rows[2]['status'], 'missing_or_unreadable')
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), before)

    def test_apex_count_never_opens_packages_or_changes_image(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            image = root / 'synthetic.img'
            with image.open('wb') as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', str(image)],
                           check=True, capture_output=True)
            fake = root / 'package.apex'
            fake.write_bytes(b'not a real APEX; never executed or opened by inventory')
            for command in ('mkdir /apex', f'write {fake} /apex/example.apex', 'mkdir /apex/another'):
                subprocess.run(['/usr/sbin/debugfs', '-w', '-R', command, str(image)],
                               check=True, capture_output=True)
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            rows = []
            audit.scan_apex_packages(image, 'vendor', rows)
            self.assertEqual(rows[0]['status'], 'read')
            self.assertEqual(rows[0]['counts']['regular_apex_or_capex'], 1)
            self.assertEqual(rows[0]['counts']['directories'], 1)
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
