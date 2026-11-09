"""Tests for source-only SUSFS 2.4/KSUN ABI research, not device tests."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_s40_susfs_abi as audit


class SusfsAbiUnitTests(unittest.TestCase):
    def test_numeric_and_kstat_conflicts_are_rejected(self):
        self.assertEqual(audit.numeric_defines(['#define CMD_SUSFS_A 0x10\n']), {'CMD_SUSFS_A': 16})
        with self.assertRaisesRegex(ValueError, 'Conflicting numeric'):
            audit.numeric_defines(['#define A 1\n', '#define A 2\n'])
        self.assertEqual(audit.kstat_flags(['#define KSTAT_SPOOF_INO (1 << 0)\n']), {'KSTAT_SPOOF_INO': 1})
        with self.assertRaisesRegex(ValueError, 'Conflicting KSTAT'):
            audit.kstat_flags(['#define KSTAT_SPOOF_INO (1 << 0)\n', '#define KSTAT_SPOOF_INO (1 << 1)\n'])

    def test_enum_and_declaration_guards(self):
        enum = 'enum UID_SCHEME { UID_A = 0, UID_B, UID_C = 5, };'
        self.assertEqual(audit.uid_scheme(enum), {'UID_A': 0, 'UID_B': 1, 'UID_C': 5})
        valid = 'struct st_susfs_example {\n bool yes;\n char name[3];\n int err;\n};\n'
        structs = audit.extract_structs([valid])
        self.assertEqual([f['name'] for f in structs['st_susfs_example']['fields']], ['yes', 'name', 'err'])
        with self.assertRaisesRegex(ValueError, 'Duplicate struct'):
            audit.extract_structs([valid, valid])
        with self.assertRaisesRegex(ValueError, 'Unexpected declaration'):
            audit.extract_structs(['struct st_susfs_example {\n void *pointer;\n};\n'])

    def test_rejects_wrong_object_or_unbounded_section(self):
        for data in (b'', b'not an ELF', b'\x7fELF\x02\x01' + b'\0' * 100):
            with self.assertRaises(ValueError):
                audit.elf_section(data, '.s40abi', 2)

    def test_source_pin_rejects_modified_file_and_symlink(self):
        with tempfile.TemporaryDirectory(prefix='s40-abi-source-test-') as temp:
            root = Path(temp)
            source = root / 'original'
            source.write_bytes(b'hello\n')
            digest = hashlib.sha256(source.read_bytes()).hexdigest()
            fake = {'sources': {'fixture': {'original': digest}}}
            with mock.patch.object(audit, 'PINS', fake):
                self.assertEqual(audit.read_checked_sources({'fixture': root})['fixture']['original'], 'hello\n')
                source.write_bytes(b'changed\n')
                with self.assertRaisesRegex(ValueError, 'SHA-256 mismatch'):
                    audit.read_checked_sources({'fixture': root})
                source.unlink()
                target = root / 'target'
                target.write_bytes(b'hello\n')
                source.symlink_to(target)
                with self.assertRaisesRegex(ValueError, 'Symlinked'):
                    audit.read_checked_sources({'fixture': root})

    def test_compare_detects_type_size_and_field_order_changes(self):
        base = {'x': {'size': 8, 'alignment': 4, 'fields': [
            {'name': 'enabled', 'type': 'bool', 'size': 1, 'offset': 0},
            {'name': 'err', 'type': 'int', 'size': 4, 'offset': 4}]}}
        changed = {'x': {'size': 8, 'alignment': 4, 'fields': [
            {'name': 'enabled', 'type': 'int', 'size': 4, 'offset': 0},
            {'name': 'err', 'type': 'int', 'size': 4, 'offset': 4}]}}
        issues = {item['issue'] for item in audit.compare_layouts(base, changed)}
        self.assertEqual(issues, {'type', 'size'})
        changed['x']['fields'].reverse()
        self.assertEqual(audit.compare_layouts(base, changed)[0]['issue'], 'field_order_or_names')

    def test_dispatcher_case_reader_ignores_comment_examples(self):
        source = '''/* case CMD_SUSFS_FAKE: */
static void process(void) {
    switch (cmd) {
    case CMD_SUSFS_REAL:
        break;
    }
}
'''
        self.assertEqual(audit.function_cases(source, 'process'), {'CMD_SUSFS_REAL'})
        with self.assertRaisesRegex(ValueError, 'missing'):
            audit.function_cases(source, 'missing')


class RealPinnedSourceTests(unittest.TestCase):
    def test_cross_compiled_arm64_source_abi(self):
        roots = {name: os.environ.get(f'S40_ABI_{name.upper()}') for name in ('kernel', 'ksun', 'susfs')}
        clang = os.environ.get('S40_ABI_CLANG') or shutil.which('clang')
        if not all(roots.values()) or not clang:
            self.skipTest('set S40_ABI_KERNEL/KSUN/SUSFS and an arm64-capable clang')
        report = audit.audit({k: Path(v) for k, v in roots.items()}, clang)
        official = report['official_2_4_source']
        self.assertEqual(official['active_userspace_commands'], 16)
        self.assertEqual(official['userspace_kernel_wire_structs_match'], 13)
        self.assertEqual(official['kstat_flag_bits_match'], 12)
        self.assertEqual(official['priority_uid_filter_command'], '0x60030')
        self.assertEqual(official['priority_uid_filter_layout']['size'], 65540)
        self.assertEqual(official['priority_uid_filter_layout']['fields'][-1]['offset'], 65536)
        lkm = report['ksun_3_4_2_separate_lkm_source']
        self.assertFalse(lkm['parent_ksun_kbuild_references_lkm'])
        self.assertEqual(lkm['active_2_4_command_names_not_handled'], [audit.PRIORITY])
        self.assertEqual(lkm['active_command_id_differences'], {})
        self.assertTrue(lkm['shares_arm64_reboot_hook_symbol_with_ksun'])
        mismatches = lkm['arm64_wire_layout_differences_against_2_4_userspace']
        self.assertIn({'struct': 'st_susfs_sus_kstat', 'field': 'is_statically', 'issue': 'size',
                       'reference': 1, 'other': 4}, mismatches)
        self.assertIn({'struct': 'st_susfs_priority_uid_filter', 'issue': 'missing', 'side': 'other'}, mismatches)
        self.assertFalse(report['susfs_2_4_integrated'])
        self.assertFalse(report['syscalls_run_or_modules_loaded'])


if __name__ == '__main__':
    unittest.main()
