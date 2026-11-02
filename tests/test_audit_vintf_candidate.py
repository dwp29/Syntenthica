"""Synthetic, host-only tests; never access a phone or modify a ROM image."""
from __future__ import annotations

import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "synthetica-project"))
import audit_vintf_candidate as audit
import test_hyperos4_lp_metadata as lp_fixture


class VintfParserTests(unittest.TestCase):
    def setUp(self):
        self.device = b'''<manifest version="2.0" type="device" target-level="4">
          <hal format="hidl"><name>android.hardware.camera.provider</name><version>2.4</version>
            <interface><name>ICameraProvider</name><instance>legacy/0</instance></interface>
          </hal>
          <hal format="aidl"><name>android.hardware.health</name><version>2</version>
            <fqname>IHealth/default</fqname></hal>
          <hal><name>vendor.example.hidden</name><version>1.0</version></hal>
        </manifest>'''
        self.framework = b'<compatibility-matrix version="2.0" type="framework" level="7"><hal><name>dummy</name></hal></compatibility-matrix>'
        self.unlevelled = b'<compatibility-matrix version="2.0" type="framework"><hal><name>dummy</name></hal></compatibility-matrix>'

    def test_manifest_parsing_reports_facts_not_raw_xml(self):
        doc = audit.parse_vintf(self.device, "vendor", "/etc/vintf/manifest.xml")
        self.assertEqual(doc["target_level"], "4")
        self.assertEqual(doc["hal_count"], 3)
        self.assertEqual(doc["hal_formats"], {"aidl": 1, "hidl": 2})
        self.assertEqual(len(doc["selected_device_hals"]), 2)
        camera = doc["selected_device_hals"][0]
        self.assertEqual(camera["versions"], ["2.4"])
        self.assertEqual(camera["interfaces"][0]["instances"], ["legacy/0"])
        self.assertNotIn("vendor.example.hidden", str(doc))
        self.assertNotIn("<manifest", str(doc))

    def test_target_level_absence_is_not_a_failure_verdict(self):
        vendor = audit.parse_vintf(self.device, "vendor", "/etc/vintf/manifest.xml")
        level7 = audit.parse_vintf(self.framework, "system", "/system/etc/vintf/compatibility_matrix.7.xml")
        generic = audit.parse_vintf(self.unlevelled, "system", "/system/etc/vintf/compatibility_matrix.device.xml")
        comparison = audit.compare_levels([vendor, level7, generic], [])
        self.assertEqual(comparison["vendor_primary_target_level"], "4")
        self.assertEqual(comparison["framework_explicit_levels_seen"], ["7"])
        self.assertEqual(comparison["visible_explicit_target_level_files"], [])
        self.assertEqual(len(comparison["visible_unlevelled_framework_matrix_files"]), 1)
        self.assertIn("not a libvintf/checkvintf", comparison["meaning"])

    def test_explicit_match_and_missing_roots_are_reported(self):
        vendor = audit.parse_vintf(self.device, "vendor", "/etc/vintf/manifest.xml")
        level4 = audit.parse_vintf(self.framework.replace(b'level="7"', b'level="4"'), "product", "/etc/vintf/matrix.xml")
        roots = [{"partition": "vendor", "path": "/odm/etc/vintf", "status": "missing_or_unreadable"}]
        comparison = audit.compare_levels([vendor, level4], roots)
        self.assertEqual(comparison["visible_explicit_target_level_files"], ["product:/etc/vintf/matrix.xml"])
        self.assertEqual(comparison["scan_roots_not_fully_read"], roots)

    def test_missing_or_ambiguous_primary_is_rejected(self):
        matrix = audit.parse_vintf(self.framework, "system", "/system/etc/vintf/compatibility_matrix.7.xml")
        vendor = audit.parse_vintf(self.device, "vendor", "/etc/vintf/manifest.xml")
        for docs in ([matrix], [vendor, vendor, matrix], [vendor]):
            with self.subTest(docs=len(docs)), self.assertRaises(audit.VintfAuditError):
                audit.compare_levels(docs, [])

    def test_xml_bombs_and_bad_syntax_are_refused(self):
        for data in (b'', b'<!DOCTYPE xml [<!ENTITY x "x">]><manifest>&x;</manifest>',
                     b'<manifest>', b'a' * (audit.MAX_XML_BYTES + 1)):
            with self.subTest(prefix=data[:15]), self.assertRaises(audit.VintfAuditError):
                audit.parse_vintf(data, "vendor", "/etc/vintf/x.xml")

    def test_xml_namespace_and_nonvintf_root(self):
        data = b'<manifest xmlns="http://example.test" type="device" target-level="4"><hal><name>android.hardware.health</name><version>2.1</version></hal></manifest>'
        parsed = audit.parse_vintf(data, "vendor", "/etc/vintf/h.xml")
        self.assertEqual(parsed["selected_device_hals"][0]["versions"], ["2.1"])
        self.assertTrue(audit.parse_vintf(b'<other/>', "vendor", "/etc/vintf/other.xml")["ignored_non_vintf_root"])


class ExtentTests(unittest.TestCase):
    def setUp(self):
        self.specs = {"system": {"bytes": 4096, "sha256": "a" * 64},
                      "vendor": {"bytes": 8192, "sha256": "b" * 64}}

    def test_metadata_validation_and_extent_selection(self):
        windows = audit.extent_windows(bytes(lp_fixture.image()), 131072, self.specs)
        self.assertEqual(windows["system"]["start"], 80 * 512)
        self.assertEqual(windows["vendor"]["end"], (96 + 16) * 512)

    def test_overlapping_or_different_copies_are_rejected(self):
        image = lp_fixture.image()
        overlapping = lp_fixture.metadata(system_sector=80, vendor_sector=84)
        image[12288:12288 + len(overlapping)] = overlapping
        image[16384:16384 + len(overlapping)] = overlapping
        with self.assertRaisesRegex(audit.VintfAuditError, "overlap"):
            audit.extent_windows(bytes(image), 131072, self.specs)
        image[16384 + 128] ^= 1
        with self.assertRaises(audit.VintfAuditError):
            audit.extent_windows(bytes(image), 131072, self.specs)

    def test_extent_fully_inside_captured_prefix_is_copied(self):
        payload = bytes(range(256)) * 40
        subset = payload[600:3000]
        windows = {"p": {"start": 600, "end": 3000, "bytes": len(subset),
                         "sha256": hashlib.sha256(subset).hexdigest()}}
        out = io.BytesIO()
        result = audit.copy_windows(io.BytesIO(payload[4096:]), payload[:4096], windows, {"p": out},
                                    len(payload), hashlib.sha256(payload).hexdigest())
        self.assertEqual(out.getvalue(), subset)
        self.assertEqual(result["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertNotIn("zip_crc_checked_at_eof", result)  # BytesIO is not a ZIP member.

    def test_window_crosses_prefix_boundary_and_whole_hash_is_required(self):
        payload = b'A' * 4096 + b'B' * 5000
        subset = payload[4000:4300]
        windows = {"p": {"start": 4000, "end": 4300, "bytes": len(subset),
                         "sha256": hashlib.sha256(subset).hexdigest()}}
        out = io.BytesIO()
        audit.copy_windows(io.BytesIO(payload[4096:]), payload[:4096], windows, {"p": out},
                           len(payload), hashlib.sha256(payload).hexdigest())
        self.assertEqual(out.getvalue(), subset)
        with self.assertRaisesRegex(audit.VintfAuditError, "super"):
            audit.copy_windows(io.BytesIO(payload[4096:]), payload[:4096], windows, {"p": io.BytesIO()},
                               len(payload), "0" * 64)
        bad_window = {"p": {**windows["p"], "sha256": "0" * 64}}
        with self.assertRaisesRegex(audit.VintfAuditError, "extent"):
            audit.copy_windows(io.BytesIO(payload[4096:]), payload[:4096], bad_window, {"p": io.BytesIO()},
                               len(payload), hashlib.sha256(payload).hexdigest())

    def test_baseline_lock_rejects_wrong_source(self):
        with self.assertRaises(audit.VintfAuditError):
            audit.part_specs({"identity": {"zip_sha256": "0" * 64}, "logical_partitions": {}})


@unittest.skipUnless(audit.pytsk3 and Path('/usr/sbin/mke2fs').exists() and Path('/usr/sbin/debugfs').exists(),
                     'Synthetic ext4 integration needs pytsk3 and e2fsprogs')
class SyntheticExt4Tests(unittest.TestCase):
    def test_read_only_inventory_with_xml_and_no_device(self):
        with tempfile.TemporaryDirectory(prefix='synthetica-vintf-synthetic-') as td:
            root = Path(td)
            image = root / 'synthetic.img'
            with image.open('wb') as f:
                f.truncate(32 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', str(image)],
                           check=True, capture_output=True)
            xml = root / 'synthetic.xml'
            xml.write_bytes(b'<manifest version="2.0" type="device" target-level="4"><hal><name>android.hardware.health</name><version>2.0</version></hal></manifest>')
            for command in ('mkdir /etc', 'mkdir /etc/vintf', f'write {xml} /etc/vintf/manifest.xml'):
                proc = subprocess.run(['/usr/sbin/debugfs', '-w', '-R', command, str(image)],
                                      check=True, capture_output=True)
                self.assertNotIn(b'error', proc.stderr.lower())
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            docs, roots = audit.scan_partition(image, 'vendor')
            self.assertEqual(hashlib.sha256(image.read_bytes()).hexdigest(), digest)
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]['target_level'], '4')
            self.assertEqual(docs[0]['selected_device_hals'][0]['name'], 'android.hardware.health')
            self.assertIn({'partition': 'vendor', 'path': '/etc/vintf', 'status': 'read'}, roots)
            self.assertIn({'partition': 'vendor', 'path': '/odm/etc/vintf', 'status': 'missing_or_unreadable'}, roots)

    def test_complete_synthetic_zip_extent_to_vintf_flow(self):
        with tempfile.TemporaryDirectory(prefix='synthetica-vintf-flow-') as td:
            root = Path(td)
            fixture = root / 'fixture.img'
            with fixture.open('wb') as f:
                f.truncate(32 * 1024 * 1024)
            subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', str(fixture)],
                           check=True, capture_output=True)
            xml = root / 'fixture.xml'
            xml.write_bytes(b'<manifest version="2.0" type="device" target-level="4"/>')
            for command in ('mkdir /etc', 'mkdir /etc/vintf', f'write {xml} /etc/vintf/manifest.xml'):
                subprocess.run(['/usr/sbin/debugfs', '-w', '-R', command, str(fixture)],
                               check=True, capture_output=True)
            partition = fixture.read_bytes()
            super_image = b'X' * 4096 + partition + b'end'
            archive = root / 'synthetic.zip'
            with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_STORED) as z:
                z.writestr('super.img', super_image)
            spec = {'vendor': {'bytes': len(partition), 'sha256': hashlib.sha256(partition).hexdigest()}}
            window = {'vendor': {'start': 4096, 'end': 4096 + len(partition), **spec['vendor']}}
            with mock.patch.object(audit, 'SUPER_BYTES', len(super_image)), \
                    mock.patch.object(audit, 'RESERVE_BYTES', 0), \
                    mock.patch.object(audit.lp, 'MAX_PREFIX', 4096), \
                    mock.patch.object(audit, 'extent_windows', return_value=window), \
                    mock.patch.object(audit.builder, 'BASE_SUPER_SHA', hashlib.sha256(super_image).hexdigest()):
                docs, roots, result = audit.audit_group(archive, root, ('vendor',), spec)
            self.assertTrue(result['super']['zip_crc_checked_at_eof'])
            self.assertEqual(result['extents']['vendor']['before'], result['extents']['vendor']['after'])
            self.assertEqual(docs[0]['target_level'], '4')
            self.assertFalse(any(p.name.startswith('vintf-partitions-') for p in root.iterdir()))


if __name__ == '__main__':
    unittest.main()
