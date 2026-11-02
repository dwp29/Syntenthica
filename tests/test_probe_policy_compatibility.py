import hashlib
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import probe_policy_compatibility as probe


class PolicyProbeUnitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='policy-probe-test-')
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def rows(self):
        return [{'name': name, 'status': 'read'} for _, _, name, required, _ in probe.FILES if required]

    def test_compiler_args_use_pinned_mapping_and_never_disable_checks(self):
        rows = self.rows() + [{'name': 'product.cil', 'status': 'read'}]
        args = probe.candidate_args(rows)
        self.assertEqual(args[0], '/policy/system.cil')
        self.assertIn('/policy/system_mapping.cil', args)
        self.assertIn('/policy/product.cil', args)
        self.assertEqual(args[args.index('-c') + 1], '30')
        self.assertNotIn('-N', args)
        self.assertLess(args.index('/policy/vendor_public.cil'), args.index('/policy/vendor.cil'))

    def test_compiler_args_require_all_required_inputs(self):
        rows = [r for r in self.rows() if r['name'] != 'vendor.cil']
        with self.assertRaises(probe.PolicyProbeError):
            probe.candidate_args(rows)
        rows = self.rows() + [{'name': 'unrelated.cil', 'status': 'read'}]
        with self.assertRaises(probe.PolicyProbeError):
            probe.candidate_args(rows)

    def test_neverallow_disabling_is_refused_before_launch(self):
        with mock.patch.object(probe.subprocess, 'Popen') as popen:
            with self.assertRaises(probe.PolicyProbeError):
                probe.compile_isolated(self.root, ['-N'], 'candidate')
            popen.assert_not_called()

    def test_reference_mode_is_labelled_and_bound_to_fixed_inputs(self):
        with mock.patch.object(probe.subprocess, 'Popen') as popen:
            bad = [
                (['/policy/system.cil'], 'reference_candidate'),
                (['/policy/system.cil', '-N', '-N'], 'reference_candidate'),
                (['/policy/vendor.cil', '-N'], 'reference_candidate'),
                (['/policy/system.cil', '-N'], 'reference_control'),
                (['/policy/control_unknown.cil', '-N'], 'reference_control'),
                (['/policy/system.cil', '-N'], 'candidate'),
            ]
            for args, mode in bad:
                with self.subTest(args=args, mode=mode), self.assertRaises(probe.PolicyProbeError):
                    probe.compile_isolated(self.root, args, mode)
            popen.assert_not_called()

    def test_reference_controls_do_not_treat_skipped_assertions_as_strict_pass(self):
        results = [
            {'tool_exit_code': 0, 'compiled_policy_sha256': 'a' * 64},
            {'tool_exit_code': 0, 'compiled_policy_sha256': 'a' * 64},
            {'tool_exit_code': 254},
        ]
        with mock.patch.object(probe, 'compile_isolated', side_effect=results) as compiler:
            result = probe.reference_controls(self.root)
        self.assertTrue(result['synthetic_binary_identical'])
        self.assertFalse(result['candidate_and_device_policy_modified'])
        self.assertEqual(result['unknown_symbol_still_rejected_exit_code'], 254)
        self.assertNotIn('-N', compiler.call_args_list[0].args[1])
        self.assertIn('-N', compiler.call_args_list[1].args[1])
        self.assertIn('-N', compiler.call_args_list[2].args[1])

    def test_vintf_extended_diagnostics_extract_only_numeric_known_errors(self):
        text = ('Framework manifest and device compatibility matrix are incompatible: '
                'Vndk version 30 is not supported. Supported versions in framework manifest are: [ 31 32 ]\n'
                'SECRET EXTRA RAW TEXT')
        result = probe.vintf_extended_diagnostics(text)
        self.assertEqual(result['unsupported_vndk_version'], '30')
        self.assertEqual(result['framework_supported_vndk_versions'], ['31', '32'])
        self.assertNotIn('SECRET', str(result))
        sdk = ('The following System SDK versions are required by device compatibility matrix '
               'but not supported by the framework manifest: [29, 30]. Supported versions are: [31, 32].')
        result = probe.vintf_extended_diagnostics(sdk)
        self.assertEqual(result['missing_system_sdk_versions'], ['29', '30'])
        self.assertEqual(result['framework_supported_system_sdk_versions'], ['31', '32'])
        self.assertIsNone(probe.vintf_extended_diagnostics('Vndk version 30 is fine')['unsupported_vndk_version'])

    def test_policy_file_write_bounded_and_no_overwrite(self):
        probe.write_policy_file(self.root, 'vendor.cil', b'policy data')
        self.assertEqual((self.root / 'vendor.cil').read_bytes(), b'policy data')
        for name, data in (('../vendor.cil', b'x'), ('x.cil', b''), ('x.cil', b'x' * (probe.MAX_CIL + 1)),
                           ('vendor.cil', b'changed')):
            with self.subTest(name=name, length=len(data)), self.assertRaises(probe.PolicyProbeError):
                probe.write_policy_file(self.root, name, data)
        self.assertEqual((self.root / 'vendor.cil').read_bytes(), b'policy data')

    def test_vendor_version_is_rechecked_against_hash_and_contents(self):
        tsk = SimpleNamespace(TSK_FS_META_FLAG_ALLOC=1, TSK_FS_META_TYPE_REG=2)
        data = b'31.0\n'
        meta = SimpleNamespace(flags=1, type=2, size=len(data))
        entry = SimpleNamespace(info=SimpleNamespace(meta=meta), read_random=lambda _o, _n: data)
        fs = SimpleNamespace(open=lambda path: entry)
        self.assertEqual(hashlib.sha256(data).hexdigest(), 'c1be93ff1e96d84c1d4f3cffbaa3654adfe996bb2c8263733d4f6aabed72b37f')
        with mock.patch.object(probe.inventory, 'pytsk3', tsk):
            result = probe.read_vendor_mapping_version(fs)
            self.assertEqual(result['value'], '31.0')
            entry.read_random = lambda _o, _n: b'30.0\n'
            with self.assertRaises(probe.PolicyProbeError):
                probe.read_vendor_mapping_version(fs)

    def test_hypothesis_changes_only_temp_xml_sepolicy_field_semantically(self):
        original = (b'<manifest version="1.0" type="device" target-level="4">'
                    b'<hal><name>example.hardware</name><version>1.0</version></hal>'
                    b'<sepolicy><version>30.0</version></sepolicy></manifest>')
        changed = probe.hypothetical_version(original, '30.0', '31.0')
        root = ET.fromstring(changed)
        self.assertEqual(root.findtext('./sepolicy/version'), '31.0')
        self.assertEqual(root.findtext('./hal/version'), '1.0')
        self.assertEqual(root.attrib['target-level'], '4')
        for invalid in (original.replace(b'30.0', b'29.0'),
                        b'<!DOCTYPE manifest><manifest/>',
                        original.replace(b'type="device"', b'type="framework"')):
            with self.subTest(invalid=invalid), self.assertRaises(probe.PolicyProbeError):
                probe.hypothetical_version(invalid, '30.0', '31.0')

    def test_hypothesis_refuses_duplicate_and_unapproved_versions(self):
        original = b'<manifest type="device"><sepolicy><version>30.0</version><version>30.0</version></sepolicy></manifest>'
        with self.assertRaises(probe.PolicyProbeError):
            probe.hypothetical_version(original, '30.0', '31.0')
        with self.assertRaises(probe.PolicyProbeError):
            probe.hypothetical_version(original, '30.0', '32.0')

    def test_vintf_hypothesis_restores_original_on_success(self):
        path = self.root / 'snapshot' / probe.MANIFEST
        path.parent.mkdir(parents=True)
        original = b'<manifest type="device"><sepolicy><version>30.0</version></sepolicy></manifest>'
        path.write_bytes(original)
        framework = self.root / 'snapshot/system_ext/etc/vintf/manifest.xml'
        framework.parent.mkdir(parents=True)
        original_framework = b'<manifest type="framework"><vendor-ndk><version>34</version></vendor-ndk></manifest>'
        framework.write_bytes(original_framework)
        observed = []
        def run(*_args):
            observed.append((ET.fromstring(path.read_bytes()).findtext('./sepolicy/version'),
                             [e.text for e in ET.fromstring(framework.read_bytes()).findall('./vendor-ndk/version')]))
            return {'tool_result': 'mock'}, ''
        with mock.patch.object(probe.check, 'run_isolated', side_effect=run):
            result = probe.test_vintf_hypothesis(self.root)
        self.assertEqual(observed, [('30.0', ['34']), ('31.0', ['34']), ('31.0', ['34', '30'])])
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(framework.read_bytes(), original_framework)
        self.assertTrue(result['temporary_snapshot_restored'])
        self.assertTrue(result['not_a_package_change'])

    def test_combined_hypothesis_restores_both_on_failure(self):
        path = self.root / 'snapshot' / probe.MANIFEST
        path.parent.mkdir(parents=True)
        original = b'<manifest type="device"><sepolicy><version>30.0</version></sepolicy></manifest>'
        path.write_bytes(original)
        framework = self.root / 'snapshot/system_ext/etc/vintf/manifest.xml'
        framework.parent.mkdir(parents=True)
        original_framework = b'<manifest type="framework"><vendor-ndk><version>34</version></vendor-ndk></manifest>'
        framework.write_bytes(original_framework)
        with mock.patch.object(probe.check, 'run_isolated', side_effect=[({}, ''), ({}, ''), RuntimeError('failure')]):
            with self.assertRaises(RuntimeError):
                probe.test_vintf_hypothesis(self.root)
        self.assertEqual(path.read_bytes(), original)
        self.assertEqual(framework.read_bytes(), original_framework)

    def test_framework_hypothesis_rejects_mismatched_baseline(self):
        valid = b'<manifest type="framework"><vendor-ndk><version>34</version></vendor-ndk></manifest>'
        changed = probe.hypothetical_framework_vndk(valid)
        self.assertEqual([x.text for x in ET.fromstring(changed).findall('./vendor-ndk/version')], ['34', '30'])
        with self.assertRaises(probe.PolicyProbeError):
            probe.hypothetical_framework_vndk(valid.replace(b'34', b'30'))

    def test_vintf_hypothesis_restores_original_even_on_failure(self):
        path = self.root / 'snapshot' / probe.MANIFEST
        path.parent.mkdir(parents=True)
        original = b'<manifest type="device"><sepolicy><version>30.0</version></sepolicy></manifest>'
        path.write_bytes(original)
        with mock.patch.object(probe.check, 'run_isolated', side_effect=[({}, ''), RuntimeError('failure')]):
            with self.assertRaises(RuntimeError):
                probe.test_vintf_hypothesis(self.root)
        self.assertEqual(path.read_bytes(), original)

    def test_compiler_controls_require_correct_categories(self):
        (self.root / 'policy').mkdir()
        outcomes = [
            {'tool_exit_code': 0, 'compiled_policy_bytes': 123, 'neverallow_diagnostic': False},
            {'tool_exit_code': 1, 'neverallow_diagnostic': False},
            {'tool_exit_code': 1, 'neverallow_diagnostic': True},
        ]
        with mock.patch.object(probe, 'compile_isolated', side_effect=outcomes):
            result = probe.controls(self.root)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(r['neverallow_checks_enabled'] for r in result))

    def test_synthetic_neverallow_failure_for_wrong_reason_is_rejected(self):
        (self.root / 'policy').mkdir()
        outcomes = [{'tool_exit_code': 0, 'compiled_policy_bytes': 1},
                    {'tool_exit_code': 1}, {'tool_exit_code': 1, 'neverallow_diagnostic': False}]
        with mock.patch.object(probe, 'compile_isolated', side_effect=outcomes):
            with self.assertRaises(probe.PolicyProbeError):
                probe.controls(self.root)


if __name__ == '__main__':
    unittest.main()
