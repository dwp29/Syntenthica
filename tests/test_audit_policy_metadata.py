import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
import audit_policy_metadata as policy
import audit_vintf_candidate as inventory


class PolicyMetadataTests(unittest.TestCase):
    def test_summary_exposes_only_numeric_version_and_comparison(self):
        private = {'vendor_mapping_version': '30.0', 'system': 'a' * 64,
                   'vendor_system': 'b' * 64, 'system_ext': 'c' * 64,
                   'vendor_system_ext': 'c' * 64, 'product': 'bad'}
        result = policy.summarize([], [], private)
        self.assertEqual(result['vendor_mapping_version'], '30.0')
        self.assertEqual(result['precompiled_digest_file_comparisons']['system'], 'both_read_different')
        self.assertEqual(result['precompiled_digest_file_comparisons']['system_ext'], 'both_read_equal')
        self.assertEqual(result['precompiled_digest_file_comparisons']['product'],
                         'not_comparable_missing_unreadable_or_invalid')
        self.assertNotIn('a' * 64, str(result))
        self.assertIsNone(policy.summarize([], [], {'vendor_mapping_version': '../bad'})['vendor_mapping_version'])

    def test_bounded_reads_reject_incomplete_and_oversized_files(self):
        class Entry:
            def read_random(self, offset, length):
                return b''
        with self.assertRaises(policy.PolicyMetadataError):
            policy._read_and_hash(Entry(), 2, False)
        with self.assertRaises(policy.PolicyMetadataError):
            policy._read_and_hash(Entry(), policy.MAX_FILE_BYTES + 1, False)
        with self.assertRaises(policy.PolicyMetadataError):
            policy._read_and_hash(Entry(), policy.MAX_TEXT_BYTES + 1, True)

    @unittest.skipUnless(inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs are required')
    def test_ext4_inventory_is_read_only_and_distinguishes_symlinks(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trees = {part: root / part for part in ('system', 'system_ext', 'vendor', 'product')}
            for tree in trees.values():
                tree.mkdir()
            def put(part, path, text):
                dest = trees[part] / path.lstrip('/')
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(text)
            put('system', '/system/etc/selinux/plat_sepolicy.cil', '(synthetic policy)')
            put('system', '/system/etc/selinux/plat_sepolicy_and_mapping.sha256', 'a' * 64 + '\n')
            put('system', '/system/etc/selinux/mapping/30.0.cil', '(synthetic mapping)')
            put('system', '/system/etc/selinux/mapping/31.0.compat.cil', '(synthetic mapping)')
            put('vendor', '/etc/selinux/plat_sepolicy_vers.txt', '30.0\n')
            put('vendor', '/etc/selinux/precompiled_sepolicy', 'synthetic policy bytes')
            put('vendor', '/etc/selinux/precompiled_sepolicy.plat_sepolicy_and_mapping.sha256', 'b' * 64 + '\n')
            symlink = trees['system'] / 'system/etc/selinux/mapping/32.0.cil'
            os.symlink('/not/followed', symlink)
            images = {}
            for part, tree in trees.items():
                image = root / (part + '.img')
                with image.open('wb') as f:
                    f.truncate(16 * 1024**2)
                subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(tree), str(image)], check=True)
                images[part] = image
            before = {part: hashlib.sha256(image.read_bytes()).hexdigest() for part, image in images.items()}
            rows, mappings, private = [], [], {}
            for part, image in images.items():
                policy.scan(image, part, rows, mappings, private)
            result = policy.summarize(rows, mappings, private)
            self.assertEqual(result['vendor_mapping_version'], '30.0')
            self.assertEqual(result['precompiled_digest_file_comparisons']['system'], 'both_read_different')
            system_map = next(item for item in mappings if item['partition'] == 'system')
            self.assertIn({'name': '30.0.cil', 'type': 'regular'}, system_map['numeric_mapping_files'])
            self.assertIn({'name': '32.0.cil', 'type': 'symlink_not_followed'}, system_map['numeric_mapping_files'])
            self.assertNotIn('(synthetic policy)', str(result))
            self.assertEqual(before, {part: hashlib.sha256(image.read_bytes()).hexdigest()
                                      for part, image in images.items()})


if __name__ == '__main__':
    unittest.main()
