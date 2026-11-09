"""Guards for selected SUSFS priority-object research; no install or boot."""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import probe_s40_susfs_priority as priority
import probe_s40_susfs_pending as pending
import probe_s40_susfs_priority_compile as probe


def digest(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def fake_patch_section(path: str) -> tuple[str, str]:
    head = f'diff --git a/{path} b/{path}\nindex 123..456 100644\n--- a/{path}\n+++ b/{path}\n'
    relevant = ('@@ -1,1 +1,4 @@\n context\n'
                f'+#ifdef {probe.FLAG}\n+research_only();\n+#endif\n')
    irrelevant = '@@ -10,1 +13,2 @@\n other\n+unrelated();\n'
    return head + relevant + irrelevant, head + relevant


class PriorityCompileGuardTests(unittest.TestCase):
    def test_selected_patch_is_pinned_and_excludes_unrelated_hunks(self):
        a, ax = fake_patch_section('block/ioprio.c')
        b, bx = fake_patch_section('kernel/sys.c')
        upstream, expected = a + b, ax + bx
        pins = {'upstream_kernel_patch_sha256': digest(upstream),
                'selected_priority_hunks_sha256': digest(expected),
                'kernel_files': {'block/ioprio.c': {'selected_hunks': 1},
                                 'kernel/sys.c': {'selected_hunks': 1}}}
        with mock.patch.object(probe, 'PINS', pins):
            self.assertEqual(probe.selected_patch(upstream), expected)
            self.assertNotIn('unrelated', probe.selected_patch(upstream))
            with self.assertRaisesRegex(ValueError, 'patch SHA-256 mismatch'):
                probe.selected_patch(upstream + 'changed')
            pins['selected_priority_hunks_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'hunks SHA-256 mismatch'):
                probe.selected_patch(upstream)

    def test_selected_patch_rejects_missing_or_duplicate_hunks(self):
        a, _ = fake_patch_section('block/ioprio.c')
        b, _ = fake_patch_section('kernel/sys.c')
        pins = {'upstream_kernel_patch_sha256': '', 'selected_priority_hunks_sha256': '0' * 64,
                'kernel_files': {'block/ioprio.c': {'selected_hunks': 1},
                                 'kernel/sys.c': {'selected_hunks': 1}}}
        with mock.patch.object(probe, 'PINS', pins):
            missing = a + b.replace(f'+#ifdef {probe.FLAG}', '+#ifdef SOME_OTHER_FEATURE')
            pins['upstream_kernel_patch_sha256'] = digest(missing)
            with self.assertRaisesRegex(ValueError, 'hunk count'):
                probe.selected_patch(missing)
            duplicate = a + b + a
            pins['upstream_kernel_patch_sha256'] = digest(duplicate)
            with self.assertRaisesRegex(ValueError, 'duplicate'):
                probe.selected_patch(duplicate)
            pins['upstream_kernel_patch_sha256'] = digest(a)
            with self.assertRaisesRegex(ValueError, 'patch is missing'):
                probe.selected_patch(a)

    def test_checked_files_reject_changes_traversal_and_symlinks(self):
        with tempfile.TemporaryDirectory(prefix='s40-priority-file-') as tmp:
            root = Path(tmp)
            (root / 'dir').mkdir()
            (root / 'dir/input').write_text('pinned\n')
            self.assertEqual(probe.checked_file(root, 'dir/input', digest('pinned\n')), 'pinned\n')
            with self.assertRaisesRegex(ValueError, 'unpinned'):
                probe.checked_file(root, 'dir/input', digest('different\n'))
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                probe.checked_file(root, '../dir/input', digest('pinned\n'))
            (root / 'link').symlink_to(root / 'dir', target_is_directory=True)
            with self.assertRaisesRegex(ValueError, 'Symlinked'):
                probe.checked_file(root, 'link/input', digest('pinned\n'))

    def test_rejects_protected_work_or_missing_marker_before_make(self):
        with self.assertRaisesRegex(ValueError, 'protected'):
            probe.checked_work(ROOT)
        with tempfile.TemporaryDirectory(prefix='s40-priority-work-') as tmp:
            work = Path(tmp)
            with self.assertRaisesRegex(ValueError, 'marker'):
                probe.checked_work(work)
            link = work.parent / (work.name + '-link')
            try:
                link.symlink_to(work, target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'symlinked'):
                    probe.checked_work(link)
            finally:
                link.unlink(missing_ok=True)
        for jobs in (0, 9, -1):
            with self.assertRaisesRegex(ValueError, 'jobs'):
                probe.compile_probe(ROOT, jobs)

    def test_work_checks_marker_sources_config_and_build_registration(self):
        with tempfile.TemporaryDirectory(prefix='s40-priority-work-') as tmp:
            work = Path(tmp)
            src, out = work / 'kernel', work / 'out'
            files = {'block/ioprio.c': 'ioprio\n', 'kernel/sys.c': 'sys\n',
                     'drivers/kernelsu/selinux/selinux.c': 'ksu-c\n',
                     'drivers/kernelsu/selinux/selinux.h': 'ksu-h\n',
                     'fs/s40_priority_original.c': 'original\n',
                     'fs/s40_priority_guarded.c': 'guarded\n',
                     'fs/s40_priority_pending.c': 'pending\n',
                     'fs/Makefile': 'obj-y += open.o\n', 'fs/Kconfig': 'menu "FS"\n'}
            for path, content in files.items():
                f = src / path
                f.parent.mkdir(parents=True, exist_ok=True)
                f.write_text(content)
            out.mkdir()
            config = 'CONFIG_ARM64=y\nCONFIG_KSU=y\nCONFIG_NOMOUNT=y\nCONFIG_LTO_NONE=y\n'
            (out / '.config').write_text(config)
            pins = {'upstream_kernel_patch_sha256': 'a', 'selected_priority_hunks_sha256': 'b',
                    'kernel_files': {p: {'research_output_sha256': digest(files[p])}
                                     for p in ('block/ioprio.c', 'kernel/sys.c')},
                    'ksun_files': {f'kernel/selinux/{ext}': digest(files[f'drivers/kernelsu/selinux/{ext}'])
                                   for ext in ('selinux.c', 'selinux.h')},
                    'generated_fragment_sha256': {mode: digest(files[path])
                                                  for mode, path in probe.OUTPUT_SOURCES.items()}}
            marker = {'scope': 'DO_NOT_LOAD_SELECTED_SOURCE_OBJECTS_ONLY',
                      'upstream_patch_sha256': 'a', 'selected_hunks_sha256': 'b',
                      'fragment_sha256': copy.deepcopy(pins['generated_fragment_sha256'])}
            marker_path = work / probe.MARKER
            marker_path.write_text(json.dumps(marker))
            with mock.patch.object(probe, 'PINS', pins), mock.patch.object(probe.s40, 'check_config') as check_config:
                self.assertEqual(probe.checked_work(work)[0], src)
                check_config.assert_called_once()
                (out / 'unsafe-link').symlink_to(src / 'fs', target_is_directory=True)
                with self.assertRaisesRegex(ValueError, 'Unexpected symlink'):
                    probe.checked_work(work)
                (out / 'unsafe-link').unlink()
                check_config.side_effect = ValueError('Unresolved configuration')
                with self.assertRaisesRegex(ValueError, 'Unresolved configuration'):
                    probe.checked_work(work)
                check_config.side_effect = None
                (out / '.config').write_text(config + f'{probe.FLAG}=y\n')
                with self.assertRaisesRegex(ValueError, 'remain absent'):
                    probe.checked_work(work)
                (out / '.config').write_text(config)
                (src / 'fs/Makefile').write_text('obj-y += s40_priority_original.o\n')
                with self.assertRaisesRegex(ValueError, 'must not be registered'):
                    probe.checked_work(work)
                (src / 'fs/Makefile').write_text(files['fs/Makefile'])
                (src / 'fs/s40_priority_original.c').write_text('tampered\n')
                with self.assertRaisesRegex(ValueError, 'unpinned'):
                    probe.checked_work(work)
                (src / 'fs/s40_priority_original.c').write_text(files['fs/s40_priority_original.c'])
                marker['fragment_sha256']['original'] = digest('forged')
                marker_path.write_text(json.dumps(marker))
                with self.assertRaisesRegex(ValueError, 'Invalid research work marker'):
                    probe.checked_work(work)

    def test_object_checks_require_calls_and_partial_link_symbols(self):
        calls = ('R_AARCH64_CALL26 000 susfs_is_priority_uid_filtered + 0\n' * 2)
        tables = {
            'sys.o': {'susfs_is_priority_uid_filtered': {'U'}},
            'ioprio.o': {'susfs_is_priority_uid_filtered': {'U'}},
            'selinux.o': {'setup_selinux': {'T'}, 'is_ksu_domain': {'T'}},
            's40_priority_original.o': {'susfs_is_priority_uid_filtered': {'T'},
                                         'setup_selinux': {'U'}, 'is_ksu_domain': {'U'}},
            's40_priority_guarded.o': {'susfs_is_priority_uid_filtered': {'T'},
                                        'setup_selinux': {'U'}, 'is_ksu_domain': {'U'}},
            's40_priority_pending.o': {'susfs_is_priority_uid_filtered': {'T'},
                                        'setup_selinux': {'U'}, 'is_ksu_domain': {'U'}},
            'pending-DO-NOT-LOAD.o': {'susfs_is_priority_uid_filtered': {'T'},
                                       'setup_selinux': {'T'}, 'is_ksu_domain': {'T'}, 'other': {'U'}},
            'original-DO-NOT-LOAD.o': {'susfs_is_priority_uid_filtered': {'T'},
                                        'setup_selinux': {'T'}, 'is_ksu_domain': {'T'}, 'other': {'U'}},
            'guarded-DO-NOT-LOAD.o': {'susfs_is_priority_uid_filtered': {'T'},
                                       'setup_selinux': {'T'}, 'is_ksu_domain': {'T'}, 'other': {'U'}},
        }
        def fake_run(command, **kwargs):
            return calls if command[0] == 'readelf' else ''
        def fake_symbols(path, nm):
            return tables[path.name]
        with mock.patch.object(probe, 'is_arm64_relocatable'), \
             mock.patch.object(probe, 'symbols', side_effect=fake_symbols), \
             mock.patch.object(probe, 'run', side_effect=fake_run):
            report = probe.verify_objects(Path('/tmp/fake-output'))
            self.assertEqual(report['unresolved_other_symbols'], {'original': 1, 'guarded': 1, 'pending': 1})
            self.assertTrue(report['research_pending_candidate_also_compiled'])
            self.assertFalse(report['pending_candidate_failed_thread_start_race_fixed'])
            tables['pending-DO-NOT-LOAD.o']['is_ksu_domain'] = {'U'}
            with self.assertRaisesRegex(ValueError, 'Expected exactly T for is_ksu_domain'):
                probe.verify_objects(Path('/tmp/fake-output'))
            tables['pending-DO-NOT-LOAD.o']['is_ksu_domain'] = {'T'}
            calls = 'R_AARCH64_CALL26 000 susfs_is_priority_uid_filtered + 0\n'
            with self.assertRaisesRegex(ValueError, 'two priority call relocations'):
                probe.verify_objects(Path('/tmp/fake-output'))
            calls += calls
            tables['original-DO-NOT-LOAD.o']['setup_selinux'] = {'U'}
            with self.assertRaisesRegex(ValueError, 'Expected exactly T for setup_selinux'):
                probe.verify_objects(Path('/tmp/fake-output'))
            tables['original-DO-NOT-LOAD.o']['setup_selinux'] = {'T'}
            del tables['original-DO-NOT-LOAD.o']['other']
            with self.assertRaisesRegex(ValueError, 'Unexpected fully resolved link'):
                probe.verify_objects(Path('/tmp/fake-output'))

    def test_arm64_object_header_and_required_symbols(self):
        with tempfile.TemporaryDirectory(prefix='s40-priority-elf-') as tmp:
            obj = Path(tmp) / 'object.o'
            header = bytearray(64)
            header[:6] = b'\x7fELF\x02\x01'
            struct.pack_into('<HH', header, 16, 1, 183)
            obj.write_bytes(header)
            probe.is_arm64_relocatable(obj)
            struct.pack_into('<H', header, 18, 62)
            obj.write_bytes(header)
            with self.assertRaisesRegex(ValueError, 'AArch64'):
                probe.is_arm64_relocatable(obj)
        probe.require_symbol({'test': {'T'}}, 'test', 'T')
        for table in ({}, {'test': {'U'}}, {'test': {'T', 'U'}}):
            with self.assertRaisesRegex(ValueError, 'Expected exactly'):
                probe.require_symbol(table, 'test', 'T')


@unittest.skipUnless(shutil.which('git'), 'git required')
class RealSourcePriorityCompileTests(unittest.TestCase):
    def test_exact_selected_hunks_and_all_three_fragments(self):
        susfs = os.environ.get('S40_ABI_SUSFS')
        if not susfs:
            self.skipTest('set S40_ABI_SUSFS to pinned source')
        root = Path(susfs)
        source = priority.checked_susfs_file(root, priority.SOURCE)
        header = priority.checked_susfs_file(root, priority.HEADER)
        patch = probe.selected_patch(probe.checked_file(root, probe.PATCH,
                                                        probe.PINS['upstream_kernel_patch_sha256']))
        self.assertEqual(patch.count(f'+#ifdef {probe.FLAG}'), 6)
        self.assertNotIn('ksu_handle_setresuid', patch)
        with tempfile.TemporaryDirectory(prefix='s40-priority-fragments-') as tmp:
            guarded = priority.apply_candidate(source, Path(tmp) / 'candidate')
            candidate = pending.apply_pending(guarded, Path(tmp) / 'pending')
        for name, text in (('original', source), ('guarded', guarded), ('pending', candidate)):
            generated = probe.fragment(text, header)
            self.assertEqual(digest(generated), probe.PINS['generated_fragment_sha256'][name])
            self.assertIn('COMPILE', generated.upper())
            self.assertIn('is_ksu_domain()', generated)
            with self.assertRaisesRegex(ValueError, 'not pinned'):
                probe.fragment(text + '\n', header)
            with self.assertRaisesRegex(ValueError, 'header is not pinned'):
                probe.fragment(text, header + '\n')


if __name__ == '__main__':
    unittest.main()
