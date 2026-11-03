"""Synthetic range/ZIP/protobuf controls; no network or ROM is used by these tests."""
import base64
import hashlib
import io
import struct
import sys
import unittest
import zipfile
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import probe_madrid_ota_reference as probe


def varint(value):
    data = bytearray()
    while value >= 0x80:
        data.append((value & 0x7f) | 0x80)
        value >>= 7
    data.append(value)
    return bytes(data)


def scalar(number, value):
    return varint(number << 3) + varint(value)


def blob(number, value):
    return varint((number << 3) | 2) + varint(len(value)) + value


def part(name, size, digest):
    return blob(1, name.encode()) + blob(7, scalar(1, size) + blob(2, digest)) + blob(8, b'operation')


def fixture_zip(*, compressed_payload=False, bad_size=False):
    manifest = scalar(3, 4096) + scalar(12, 0) + blob(13, part('system', 1234, b's' * 32))
    manifest += blob(13, part('vendor', 5678, b'v' * 32))
    signature = b'fake metadata signature'
    header = b'CrAU' + struct.pack('>QQI', 2, len(manifest), len(signature))
    payload = header + manifest + signature + b'fake payload data'
    b64 = lambda b: base64.b64encode(b).decode()
    props = (f'FILE_HASH={b64(hashlib.sha256(payload).digest())}\n'
             f'FILE_SIZE={len(payload) + int(bad_size)}\n'
             f'METADATA_HASH={b64(hashlib.sha256(header + manifest).digest())}\n'
             f'METADATA_SIZE={len(header) + len(manifest)}\n').encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', allowZip64=True) as z:
        z.writestr('META-INF/com/android/metadata', b'ota-type=AB\npre-device=madrid\npost-sdk-level=37\n')
        z.writestr('payload_properties.txt', props, compress_type=zipfile.ZIP_DEFLATED)
        z.writestr('payload.bin', payload, compress_type=zipfile.ZIP_DEFLATED if compressed_payload else zipfile.ZIP_STORED)
    return buffer.getvalue()


class MemoryRange:
    def __init__(self, data):
        self.data, self.total = data, len(data)
        self.requests, self.received = 0, 0
        self.etag, self.modified, self.url = '"synthetic"', 'today', probe.URLS[0]

    def fetch(self, start, end):
        self.requests += 1
        self.received += end - start + 1
        return self.data[start:end + 1]


class RangeAndPayloadTests(unittest.TestCase):
    def test_small_synthetic_zip_metadata_and_declared_partition_hashes(self):
        source = MemoryRange(fixture_zip())
        result = probe.inspect_zip(probe.RangeReader(source))
        self.assertEqual(result['metadata_fields']['pre-device'], 'madrid')
        self.assertEqual(result['metadata_fields']['post-sdk-level'], '37')
        self.assertTrue(result['metadata_zip_crc_verified'])
        self.assertTrue(result['payload_properties_zip_crc_verified'])
        self.assertTrue(result['advertised_metadata_hash_matches_header_manifest'])
        self.assertTrue(result['advertised_metadata_size_matches_header_manifest'])
        self.assertFalse(result['advertised_metadata_hash_matches_including_signature'])
        self.assertEqual(result['manifest']['partitions'][0]['declared_new_sha256'], (b's' * 32).hex())
        self.assertGreater(source.requests, 1)
        self.assertLess(source.received, probe.MAX_TOTAL)

    def test_refuses_server_ignoring_range_or_changing_total_and_etag(self):
        good = {'Content-Range': 'bytes 2-4/10', 'ETag': '"A"', 'Last-Modified': 'today'}
        self.assertEqual(probe.validate_range(206, good, b'abc', 2, 4, 10, '"A"', 'today')[0], 10)
        with self.assertRaisesRegex(probe.ProbeError, 'partial-content'):
            probe.validate_range(200, good, b'abc', 2, 4, 10, '"A"', 'today')
        with self.assertRaisesRegex(probe.ProbeError, 'ETag changed'):
            probe.validate_range(206, good, b'abc', 2, 4, 10, '"B"', 'today')
        with self.assertRaisesRegex(probe.ProbeError, 'size changed'):
            probe.validate_range(206, good, b'abc', 2, 4, 11, '"A"', 'today')
        with self.assertRaisesRegex(probe.ProbeError, 'content encoding'):
            probe.validate_range(206, {**good, 'Content-Encoding': 'gzip'}, b'abc', 2, 4, 10, '"A"', 'today')

    def test_reader_bounds_and_short_response(self):
        source = MemoryRange(b'abc')
        reader = probe.RangeReader(source)
        self.assertEqual(reader.read(2), b'ab')
        self.assertEqual(reader.seek(-1, io.SEEK_END), 2)
        self.assertEqual(reader.read(), b'c')
        with self.assertRaisesRegex(probe.ProbeError, 'outside'):
            reader.seek(4)
        source.total = probe.MAX_REQUEST + 1
        reader.seek(0)
        with self.assertRaisesRegex(probe.ProbeError, 'oversized'):
            reader.read()
        reader.seek(0)
        with self.assertRaisesRegex(probe.ProbeError, 'Short range'):
            reader.read(4)

    def test_compressed_payload_and_wrong_size_are_inconclusive(self):
        for data, reason in ((fixture_zip(compressed_payload=True), 'stored ZIP member'),
                             (fixture_zip(bad_size=True), 'size does not match')):
            with self.subTest(reason=reason), self.assertRaisesRegex(probe.ProbeError, reason):
                probe.inspect_zip(probe.RangeReader(MemoryRange(data)))

    def test_manifest_rejects_duplicate_names_wrong_hash_and_corrupt_wire(self):
        duplicate = blob(13, part('system', 1, b'a' * 32)) * 2
        with self.assertRaisesRegex(probe.ProbeError, 'duplicate partition'):
            probe.parse_manifest(duplicate)
        with self.assertRaisesRegex(probe.ProbeError, 'SHA-256-sized'):
            probe.parse_manifest(blob(13, part('system', 1, b'short')))
        for bad in (b'\x80', b'\x0a\x03x', b'\x0b', b'\x00'):
            with self.subTest(bad=bad), self.assertRaises(probe.ProbeError):
                probe.parse_manifest(bad)

    def test_public_partition_names_with_dot_and_hyphen_are_supported_but_paths_rejected(self):
        parsed = probe.parse_manifest(blob(13, part('image-a.b', 1, b'a' * 32)))
        self.assertEqual(parsed['partitions'][0]['name'], 'image-a.b')
        with self.assertRaisesRegex(probe.ProbeError, 'character codes'):
            probe.parse_manifest(blob(13, part('../invalid', 1, b'a' * 32)))

    def test_snapshot_comparison_does_not_claim_file_origin(self):
        parsed = probe.parse_manifest(blob(13, part('system', 1234, b's' * 32)))
        rows = {row['partition']: row for row in probe.compare_snapshot(parsed)}
        self.assertEqual(rows['system']['comparison'], 'different_sizes_not_a_whole_partition_match')
        self.assertEqual(rows['vendor']['comparison'], 'not_comparable_manifest_field_absent')
        self.assertIsNone(rows['vendor']['reference_declared_sha256'])

    def test_probe_uses_only_synthetic_range_and_reports_limitations(self):
        source = MemoryRange(fixture_zip())
        with mock.patch.object(probe, 'HttpRanges', return_value=source):
            result = probe.probe()
        self.assertEqual(result['status'], 'partial_unverified_reference_metadata_only_not_a_rom_or_flash_approval')
        self.assertFalse(result['catalog_md5_verified'])
        self.assertTrue(any('not independently authenticated' in item for item in result['limitations']))
        self.assertTrue(any('No full ROM' in item for item in result['limitations']))

    def test_http_transport_uses_only_exact_ranges_and_pins_etag(self):
        content = fixture_zip()
        calls = []
        class Response:
            status = 206
            def __init__(self, first, last):
                self.first, self.last = first, last
                self.headers = {'Content-Range': f'bytes {first}-{last}/{len(content)}',
                                'ETag': '"synthetic-strong"', 'Last-Modified': 'today'}
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): return content[self.first:self.last + 1]
        class Opener:
            def open(self, request, timeout):
                self.assertEqual(request.get_header('Accept-encoding'), 'identity')
                first, last = map(int, request.get_header('Range').removeprefix('bytes=').split('-'))
                if calls:
                    self.assertEqual(request.get_header('If-match'), '"synthetic-strong"')
                calls.append((first, last))
                return Response(first, last)
        Opener.assertEqual = self.assertEqual
        with mock.patch.object(probe.urllib.request, 'build_opener', return_value=Opener()):
            source = probe.HttpRanges(probe.URLS[0])
            result = probe.inspect_zip(probe.RangeReader(source))
        self.assertEqual(calls[0], (0, 0))
        self.assertEqual(result['manifest']['partitions'][0]['name'], 'system')
        self.assertLessEqual(source.received, probe.MAX_TOTAL)
        self.assertLessEqual(len(calls), probe.MAX_REQUESTS)

    def test_http_200_is_rejected_before_reading_any_full_body(self):
        class Response:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def read(self, size): raise AssertionError('Must not read a whole response')
        class Opener:
            def open(self, request, timeout): return Response()
        with mock.patch.object(probe.urllib.request, 'build_opener', return_value=Opener()):
            with self.assertRaisesRegex(probe.ProbeError, 'partial-content'):
                probe.HttpRanges(probe.URLS[0])

    def test_non_whitelisted_network_destination_is_refused(self):
        with self.assertRaisesRegex(probe.ProbeError, 'outside the fixed public catalog'):
            probe.HttpRanges('https://example.com/anything')


if __name__ == '__main__':
    unittest.main()
