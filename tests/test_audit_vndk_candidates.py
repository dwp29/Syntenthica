"""Synthetic read-only tests; no phone or actual ROM is used."""
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_vndk_candidates as audit


TSK = SimpleNamespace(TSK_FS_META_FLAG_ALLOC=1, TSK_FS_NAME_FLAG_ALLOC=1,
                      TSK_FS_META_TYPE_REG=2, TSK_FS_META_TYPE_DIR=3, TSK_FS_META_TYPE_LNK=4)


def entry(kind, data=b'', *, name=None, link=None, allocated=True, size=None):
    meta = SimpleNamespace(flags=1 if allocated else 0, type=kind, addr=42,
                           size=len(data) if size is None else size, link=link)
    info_name = None if name is None else SimpleNamespace(name=name, flags=1)
    return SimpleNamespace(info=SimpleNamespace(meta=meta, name=info_name),
                           read_random=lambda offset, length: data[offset:offset + length])


class VndkAuditTests(unittest.TestCase):
    def test_extracts_selected_properties_without_raw_content(self):
        raw = (b'# sample\nro.vndk.version=30\nro.vendor.build.version.sdk=30\n'
               b'ro.other.private=do_not_report\n')
        actual = audit.parse_properties(raw)
        self.assertEqual(actual, {'ro.vndk.version': '30', 'ro.vendor.build.version.sdk': '30'})
        self.assertNotIn('do_not_report', str(actual))
        for bad in (b'ro.vndk.version=30\nro.vndk.version=31\n', b'ro.vndk.version=x y\n'):
            with self.subTest(bad=bad), self.assertRaises(audit.VndkAuditError):
                audit.parse_properties(bad)

    def test_vintf_versions_and_library_counts_only(self):
        data = (b'<compatibility-matrix type="device"><vendor-ndk><version>30</version>'
                b'<library>libfoo.so</library><library>android.hidl.base@1.0.so</library>'
                b'</vendor-ndk></compatibility-matrix>')
        result = audit.parse_vndk_xml(data, 'compatibility-matrix', 'device')
        self.assertEqual(result['vendor_ndk'][0]['version'], '30')
        self.assertEqual(result['vendor_ndk'][0]['library_count'], 2)
        self.assertEqual(result['xml_sha256'], hashlib.sha256(data).hexdigest())
        for bad in (data.replace(b'30', b'XX'), data.replace(b'libfoo.so', b'../libfoo.so'),
                    b'<!DOCTYPE a><manifest/>', data.replace(b'type="device"', b'type="framework"')):
            with self.subTest(bad=bad), self.assertRaises((audit.VndkAuditError, ValueError)):
                audit.parse_vndk_xml(bad, 'compatibility-matrix', 'device')

    def test_only_names_matching_vndk_apex_are_hashed(self):
        root = entry(TSK.TSK_FS_META_TYPE_DIR)
        package = entry(TSK.TSK_FS_META_TYPE_REG, b'fake-apex', name=b'com.android.vndk.v30.apex')
        symlink = entry(TSK.TSK_FS_META_TYPE_LNK, name=b'com.android.vndk.v31.capex', link=b'/elsewhere')
        other = entry(TSK.TSK_FS_META_TYPE_REG, b'ignore', name=b'com.android.runtime.apex')
        link = entry(TSK.TSK_FS_META_TYPE_LNK, link=b'/apex/com.android.vndk.v30/lib64')
        properties = entry(TSK.TSK_FS_META_TYPE_REG, b'ro.vndk.version=30\n')
        objects = {'/system/apex': root, '/system/lib64/vndk-30': link, '/system/build.prop': properties}
        opened = []
        def open_file(path):
            opened.append(path)
            if path not in objects:
                raise OSError('missing')
            return objects[path]
        fs = SimpleNamespace(open=open_file, open_dir=lambda inode: [package, symlink, other])
        with mock.patch.object(audit.inventory, 'pytsk3', TSK):
            result = audit.scan_fs(fs, 'system')
        packages = result['apex_directory']['packages']
        self.assertEqual([p['name'] for p in packages], ['com.android.vndk.v30.apex', 'com.android.vndk.v31.capex'])
        self.assertEqual(packages[0]['sha256'], hashlib.sha256(b'fake-apex').hexdigest())
        self.assertEqual(packages[1]['status'], 'symlink_not_followed')
        self.assertEqual(result['vndk30_links'][2]['target'], '/apex/com.android.vndk.v30/lib64')
        self.assertNotIn('/apex/com.android.vndk.v30/lib64', opened)
        self.assertEqual(result['selected_properties'][0]['selected'], {'ro.vndk.version': '30'})

    def test_unallocated_and_oversized_apex_are_not_read(self):
        root = entry(TSK.TSK_FS_META_TYPE_DIR)
        package = entry(TSK.TSK_FS_META_TYPE_REG, b'', name=b'com.android.vndk.v30.apex',
                        size=audit.MAX_APEX + 1)
        fs = SimpleNamespace(open=lambda path: root if path == '/apex' else None,
                             open_dir=lambda inode: [package])
        with mock.patch.object(audit.inventory, 'pytsk3', TSK), self.assertRaises(audit.VndkAuditError):
            audit.scan_fs(fs, 'system_ext')
        package.info.meta.flags = 0
        with mock.patch.object(audit.inventory, 'pytsk3', TSK):
            result = audit.scan_fs(fs, 'system_ext')
        self.assertEqual(result['apex_directory']['packages'][0]['status'], 'unallocated')
        self.assertNotIn('sha256', result['apex_directory']['packages'][0])

    def test_snapshot_declarations_require_verified_hashes(self):
        samples = [
            ('/system/etc/vintf/manifest.xml', b'<manifest type="framework"/>'),
            ('/system_ext/etc/vintf/manifest.xml', b'<manifest type="framework"/>'),
            ('/vendor/etc/vintf/compatibility_matrix.xml', b'<compatibility-matrix type="device"/>'),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            seen = {}
            for guest, data in samples:
                path = root / guest.lstrip('/')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                seen[guest] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
            self.assertEqual(len(audit.snapshot_declarations(root, seen)), 3)
            (root / samples[0][0].lstrip('/')).write_bytes(b'altered')
            with self.assertRaises(audit.VndkAuditError):
                audit.snapshot_declarations(root, seen)


@unittest.skipUnless(audit.inventory.pytsk3 and Path('/usr/sbin/mke2fs').exists()
                     and Path('/usr/sbin/debugfs').exists(), 'Synthetic ext4 tools are required')
class VndkExt4Tests(unittest.TestCase):
    def test_real_reader_never_modifies_synthetic_extent(self):
        with tempfile.TemporaryDirectory(prefix='vndk-ext4-test-') as temp:
            root = Path(temp)
            image = root / 'synthetic.img'
            with image.open('wb') as stream:
                stream.truncate(32 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', str(image)],
                           check=True, capture_output=True)
            (root / 'fixture-apex').write_bytes(b'synthetic apex bytes, not installed')
            (root / 'fixture-props').write_bytes(b'ro.vndk.version=30\n')
            commands = [
                'mkdir /system', 'mkdir /system/apex', 'mkdir /system/lib64',
                f'write {root}/fixture-apex /system/apex/com.android.vndk.v30.apex',
                f'write {root}/fixture-props /system/build.prop',
                'symlink /system/lib64/vndk-30 /apex/com.android.vndk.v30/lib64',
            ]
            for command in commands:
                proc = subprocess.run(['/usr/sbin/debugfs', '-w', '-R', command, str(image)],
                                      check=True, capture_output=True, text=True)
                self.assertNotIn('error', proc.stderr.lower(), proc.stderr)
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            result = audit.scan_partition(image, 'system')
            self.assertEqual(result['apex_directory']['packages'][0]['version'], '30')
            self.assertEqual(result['selected_properties'][0]['selected']['ro.vndk.version'], '30')
            self.assertEqual(result['vndk30_links'][2]['target'], '/apex/com.android.vndk.v30/lib64')
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), before)


if __name__ == '__main__':
    unittest.main()
