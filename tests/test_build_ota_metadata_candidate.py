import contextlib
import hashlib
import os
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import build_ota_metadata_candidate as ota


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        while block := f.read(1024 * 1024):
            h.update(block)
    return h.hexdigest()


def make_metadata(value='metadata:69:368,metadata.pb:505:282                 '):
    p = ota.ota_metadata_pb2.OtaMetadata()
    p.type = ota.ota_metadata_pb2.OtaMetadata.BLOCK
    p.property_files['ota-property-files'] = value
    p.precondition.device.append('joyeuse')
    p.postcondition.sdk_level = '35'
    p.postcondition.timestamp = 1783296113
    # Unknown fields must survive the protobuf rewrite.
    pb = p.SerializeToString(deterministic=True) + b'\xa0\x06\x01'
    text = ('ota-property-files=' + value + '\n'
            'ota-required-cache=0\nota-type=BLOCK\npost-sdk-level=35\npre-device=joyeuse\n').encode()
    return text, pb


def fixture(path):
    text, pb = make_metadata()
    script = b's' * 1569
    contents = {
        ota.previous.SCRIPT: script,
        'super.img': b'large fake super image' * 400,
        'META-INF/': None,
        'boot.img': b'boot contents' * 100,
        'dtbo.img': b'dtbo contents' * 50,
        'META-INF/com/': None,
        'META-INF/com/android/': None,
        'META-INF/com/google/': None,
        ota.METADATA: text,
        ota.METADATA_PB: pb,
        'META-INF/com/android/otacert': b'certificate data',
        'META-INF/com/google/android/': None,
        ota.audit.BINARY: b'updater binary fixture',
    }
    specs = {}
    with zipfile.ZipFile(path, 'x', allowZip64=True) as z:
        for name, data in contents.items():
            if data is None:
                z.writestr(name, b'', compress_type=zipfile.ZIP_STORED)
                specs[name] = {'name': name, 'directory': True}
            else:
                z.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=1)
                specs[name] = {'name': name, 'bytes': len(data), 'sha256': sha(data)}
    return specs, contents


@contextlib.contextmanager
def configured(source, specs, script):
    overrides = {'BASE_BYTES': source.stat().st_size, 'BASE_SHA': file_sha(source)}
    with mock.patch.multiple(ota, **overrides), \
         mock.patch.object(ota.previous, 'NEW_SCRIPT_SHA', sha(script)), \
         mock.patch.object(ota.previous, 'expectations', return_value=specs):
        yield


class OtaMetadataTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='synthetica-ota-test-')
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.source = self.dir / '02.zip'
        self.output = self.dir / '03.zip'
        self.specs, self.contents = fixture(self.source)
        self.oldsha = file_sha(self.source)

    def build(self):
        with configured(self.source, self.specs, self.contents[ota.previous.SCRIPT]):
            return ota.build(self.source, self.output, self.dir / 'lock')

    def test_build_repairs_both_formats_and_preserves_every_other_stream(self):
        report = self.build()
        self.assertEqual(file_sha(self.source), self.oldsha)
        self.assertEqual(report['source']['sha256'], self.oldsha)
        self.assertEqual(report['output']['sha256'], file_sha(self.output))
        self.assertEqual(report['status'], 'host_verified_not_device_tested_not_flash_approved')
        self.assertFalse(report['output']['signed_by_this_recipe'])
        self.assertTrue(report['source_all_member_hashes_and_crc_verified'])
        self.assertTrue(report['unchanged_member_compressed_streams_identical'])
        self.assertEqual(len(report['ota_metadata_verification']['property_files']), 2)
        with zipfile.ZipFile(self.source) as old, zipfile.ZipFile(self.output) as new:
            self.assertEqual(set(old.namelist()), set(new.namelist()))
            self.assertEqual(new.comment, b'')
            for name, content in self.contents.items():
                if name not in ota.CHANGED and content is not None:
                    self.assertEqual(new.read(name), old.read(name), name)
                if name in ota.CHANGED:
                    self.assertEqual(new.getinfo(name).compress_type, zipfile.ZIP_STORED)
                    self.assertNotEqual(old.read(name), new.read(name))
            old_infos = {i.filename: i for i in old.infolist()}
            new_infos = {i.filename: i for i in new.infolist()}
            ota.compare_compressed(self.source, self.output, old_infos, new_infos)
            t, p = new.read(ota.METADATA), new.read(ota.METADATA_PB)
            props, _ = ota.property_values(t, p)
            self.assertEqual(len(props['ota-property-files']), ota.RESERVED)
            self.assertEqual(ota.nonproperty_proto(ota.parse_proto(p)),
                             ota.nonproperty_proto(ota.parse_proto(self.contents[ota.METADATA_PB])))
            self.assertTrue(ota.parse_proto(p).SerializeToString().endswith(b'\xa0\x06\x01'))
        check = ota.verify_ota(self.output, self.contents[ota.METADATA], self.contents[ota.METADATA_PB])
        self.assertTrue(all(x['stored'] and x['direct_range_matches'] for x in check['property_files']))
        self.assertFalse((self.dir / '03.zip.partial').exists())

    def test_zip64_local_and_central_records_with_small_synthetic_limit(self):
        source = self.dir / 'source-zip64.zip'
        output = self.dir / 'output-zip64.zip'
        with mock.patch.object(zipfile, 'ZIP64_LIMIT', 512):
            specs, contents = fixture(source)
            with configured(source, specs, contents[ota.previous.SCRIPT]):
                report = ota.build(source, output, self.dir / 'lock')
            self.assertTrue(report['unchanged_member_compressed_streams_identical'])
            layout, _ = ota.audit.archive_info(output)
            self.assertGreater(layout['central_directory_offset'], 512)
            self.assertTrue(any(row['central_zip64_payload_bytes'] for row in layout['entries']))
            self.assertTrue(any(row['local_zip64_payload_bytes'] for row in layout['entries']))
            self.assertTrue(all(r['direct_range_matches'] for r in report['ota_metadata_verification']['property_files']))

    def test_wrong_source_hash_refused_without_output(self):
        with configured(self.source, self.specs, self.contents[ota.previous.SCRIPT]), \
             mock.patch.object(ota, 'BASE_SHA', '0' * 64):
            with self.assertRaises(ota.previous.GuardBuildError):
                ota.build(self.source, self.output, self.dir / 'lock')
        self.assertFalse(self.output.exists())
        self.assertEqual(file_sha(self.source), self.oldsha)

    def test_existing_output_and_partial_are_never_overwritten(self):
        with configured(self.source, self.specs, self.contents[ota.previous.SCRIPT]):
            self.output.write_bytes(b'keep')
            with self.assertRaises(ota.OtaBuildError):
                ota.build(self.source, self.output, self.dir / 'lock')
            self.assertEqual(self.output.read_bytes(), b'keep')
            self.output.unlink()
            partial = self.dir / '03.zip.partial'
            partial.write_bytes(b'keep partial')
            with self.assertRaises(ota.OtaBuildError):
                ota.build(self.source, self.output, self.dir / 'lock')
            self.assertEqual(partial.read_bytes(), b'keep partial')

    def test_output_symlink_is_rejected(self):
        self.output.symlink_to(self.dir / 'missing')
        with configured(self.source, self.specs, self.contents[ota.previous.SCRIPT]):
            with self.assertRaises(ota.OtaBuildError):
                ota.build(self.source, self.output, self.dir / 'lock')

    def test_bad_member_hash_refuses_output(self):
        self.specs['boot.img']['sha256'] = '0' * 64
        with configured(self.source, self.specs, self.contents[ota.previous.SCRIPT]):
            with self.assertRaises(ota.previous.GuardBuildError):
                ota.build(self.source, self.output, self.dir / 'lock')
        self.assertFalse(self.output.exists())
        self.assertEqual(file_sha(self.source), self.oldsha)

    def test_mismatched_text_and_protobuf_values_rejected(self):
        t, p = make_metadata()
        with self.assertRaises(ota.OtaBuildError):
            ota.property_values(t.replace(b'metadata:69:', b'metadata:68:'), p)

    def test_duplicate_legacy_key_rejected(self):
        t, p = make_metadata()
        with self.assertRaises(ota.OtaBuildError):
            ota.property_values(t + b'ota-type=BLOCK\n', p)

    def test_extra_or_missing_token_rejected(self):
        for value in ('metadata:1:2', 'metadata:1:2,metadata:3:4',
                      'metadata:1:2,metadata.pb:3:4,payload.bin:1:8',
                      'metadata:one:2,metadata.pb:3:4'):
            with self.subTest(value=value):
                t, p = make_metadata(value)
                with self.assertRaises(ota.OtaBuildError):
                    ota.property_values(t, p)

    def test_unexpected_property_key_rejected(self):
        t, p = make_metadata()
        msg = ota.parse_proto(p)
        msg.property_files['something-property-files'] = 'metadata:1:1,metadata.pb:2:2'
        with self.assertRaises(ota.OtaBuildError):
            ota.property_values(t, msg.SerializeToString())

    def test_malformed_or_truncated_proto_rejected(self):
        with self.assertRaises(ota.OtaBuildError):
            ota.parse_proto(b'\x22\xff')
        with self.assertRaises(ota.OtaBuildError):
            ota.parse_proto(b'')

    def test_direct_range_tamper_is_detected(self):
        self.build()
        with zipfile.ZipFile(self.output) as archive:
            info = archive.getinfo(ota.METADATA)
        with self.output.open('r+b') as f:
            offset = ota.previous._raw_data_offset(f, info)
            f.seek(offset)
            b = f.read(1)
            f.seek(offset)
            f.write(bytes([b[0] ^ 1]))
        with self.assertRaises((ota.OtaBuildError, zipfile.BadZipFile)):
            ota.verify_ota(self.output, self.contents[ota.METADATA], self.contents[ota.METADATA_PB])

    def test_changed_compressed_stream_detected(self):
        self.build()
        with zipfile.ZipFile(self.source) as old, zipfile.ZipFile(self.output) as new:
            old_infos = {i.filename: i for i in old.infolist()}
            new_infos = {i.filename: i for i in new.infolist()}
        with self.output.open('r+b') as f:
            offset = ota.previous._raw_data_offset(f, new_infos['boot.img'])
            f.seek(offset)
            b = f.read(1)
            f.seek(offset)
            f.write(bytes([b[0] ^ 1]))
        with self.assertRaises(ota.OtaBuildError):
            ota.compare_compressed(self.source, self.output, old_infos, new_infos)

    def test_proto_nonproperty_mutation_is_detected(self):
        t, p = make_metadata()
        msg = ota.parse_proto(p)
        msg.postcondition.sdk_level = '99'
        self.assertNotEqual(ota.nonproperty_proto(ota.parse_proto(p)), ota.nonproperty_proto(msg))

    def test_no_reserved_value_overflow(self):
        with mock.patch.object(ota, 'RESERVED', 3):
            with zipfile.ZipFile(self.source) as archive:
                infos = {i.filename: i for i in archive.infolist()}
                with self.assertRaises(ota.OtaBuildError):
                    ota.planned_metadata(self.contents[ota.METADATA], self.contents[ota.METADATA_PB], infos)


if __name__ == '__main__':
    unittest.main()
