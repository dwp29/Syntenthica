#!/usr/bin/env python3
"""Bounded public-catalog metadata probe; never download or install a donor ROM.

Fetch at most a small number of exact byte ranges from a fixed Xiaomi CDN URL,
read only ZIP directory/OTA metadata and the payload manifest, and compare the
manifest's DECLARED partition hashes with the previously measured port snapshot.
The catalog's MD5 is not validated by range requests. Results are untrusted leads,
not provenance, signature, compatibility or flash approval.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import struct
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = ROOT / 'research/hyperos4/HASIL-POLICY-COMPAT-RUN-41485767990-2026-11-02.json'
SNAPSHOT_SHA256 = '08a6a4ba4130344a545fd3841b7a99b2477d656a6550879df85b6af80f7a5f68'
BUILD_REPORT = ROOT / 'research/hyperos4/HASIL-BUILD-03-RUN-41477695884-2026-11-02.json'
BUILD_REPORT_SHA256 = '23a195d558090fb0673b9650c4a16f29d46454d2811020ff292291ca5e8a04a8'
TARGET = 'madrid-ota_full-OS4.0.17.0.XEOCNXM-user-17.0-c38824c8fe.zip'
URLS = tuple(f'https://{host}/OS4.0.17.0.XEOCNXM/{TARGET}'
             for host in ('cdnorg.d.miui.com', 'bigota.d.miui.com', 'hugeota.d.miui.com'))
CATALOG = ('https://github.com/XiaomiFirmwareUpdater/xmfirmwareupdater.github.io/blob/'
           'aec2464da65583892b2ac1a319fd583df1197d96/pages/hyperos/updates/madrid/'
           'OS4.0.17.0.XEOCNXM.md')
MAX_REQUEST = 8 * 1024 * 1024
MAX_TOTAL = 16 * 1024 * 1024
MAX_REQUESTS = 32
MAX_SMALL = 64 * 1024
MAX_MANIFEST = 4 * 1024 * 1024
MAX_SIGNATURE = 256 * 1024
MAX_CATALOG_SIZE = 100 * 1024**3
LOCAL = struct.Struct('<4sHHHHHIIIHH')


class ProbeError(Exception):
    """Remote or manifest is unavailable, unsafe, too large, or unsupported."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ProbeError('Redirect refused; only the fixed public CDN URLs are permitted')


def validate_range(status, headers, body: bytes, start: int, end: int,
                   total: int | None, etag: str | None, modified: str | None):
    if status != 206:
        raise ProbeError('Server did not honour a partial-content request')
    match = re.fullmatch(r'bytes (\d+)-(\d+)/(\d+)', headers.get('Content-Range', ''))
    if not match:
        raise ProbeError('Invalid Content-Range')
    first, last, seen_total = map(int, match.groups())
    if (first != start or last != end or end >= seen_total or len(body) != end - start + 1
            or not 0 < seen_total <= MAX_CATALOG_SIZE or (total is not None and seen_total != total)):
        raise ProbeError('Range or total size changed or did not match the request')
    if headers.get('Content-Encoding', 'identity').lower() != 'identity':
        raise ProbeError('Unexpected HTTP content encoding')
    seen_etag, seen_modified = headers.get('ETag'), headers.get('Last-Modified')
    if etag is not None and seen_etag != etag:
        raise ProbeError('Remote ETag changed during the inspection')
    if modified is not None and seen_modified != modified:
        raise ProbeError('Remote Last-Modified changed during the inspection')
    return seen_total, seen_etag, seen_modified


class HttpRanges:
    def __init__(self, url: str):
        if url not in URLS:
            raise ProbeError('URL is outside the fixed public catalog')
        self.url, self.total, self.etag, self.modified = url, None, None, None
        self.requests, self.received = 0, 0
        self.opener = urllib.request.build_opener(NoRedirect())
        self.fetch(0, 0)  # Discover size without a HEAD or whole-file download.

    def fetch(self, start: int, end: int) -> bytes:
        size = end - start + 1
        if (start < 0 or size < 1 or size > MAX_REQUEST or self.requests >= MAX_REQUESTS
                or self.received + size > MAX_TOTAL or (self.total is not None and end >= self.total)):
            raise ProbeError('Range exceeds the bounded network budget')
        headers = {'Range': f'bytes={start}-{end}', 'Accept-Encoding': 'identity',
                   'User-Agent': 'Synthetica-public-reference-metadata-probe/1'}
        if self.etag and not self.etag.startswith('W/'):
            headers['If-Match'] = self.etag
        request = urllib.request.Request(self.url, headers=headers, method='GET')
        try:
            with self.opener.open(request, timeout=30) as response:
                if response.status != 206:
                    raise ProbeError('Server did not honour a partial-content request')
                data = response.read(size + 1)
                found = validate_range(response.status, response.headers, data, start, end,
                                       self.total, self.etag, self.modified)
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise ProbeError(f'CDN range request unavailable ({type(exc).__name__})') from exc
        self.requests += 1
        self.received += len(data)
        if self.total is None:
            self.total, self.etag, self.modified = found
        return data


class RangeReader(io.RawIOBase):
    """File-like random access over a bounded, already initialized range source."""
    def __init__(self, source):
        super().__init__()
        self.source, self.pos = source, 0

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self.pos

    def seek(self, offset, whence=io.SEEK_SET):
        if whence == io.SEEK_SET:
            position = offset
        elif whence == io.SEEK_CUR:
            position = self.pos + offset
        elif whence == io.SEEK_END:
            position = self.source.total + offset
        else:
            raise ProbeError('Unsupported seek mode')
        if not 0 <= position <= self.source.total:
            raise ProbeError('ZIP seek is outside the remote object')
        self.pos = position
        return self.pos

    def read(self, size=-1):
        remaining = self.source.total - self.pos
        if size is None or size < 0:
            size = remaining
        size = min(size, remaining)
        if size > MAX_REQUEST:
            raise ProbeError('ZIP parser requested an oversized range')
        if not size:
            return b''
        data = self.source.fetch(self.pos, self.pos + size - 1)
        if len(data) != size:
            raise ProbeError('Short range response')
        self.pos += size
        return data


def _varint(data: memoryview, position: int):
    value = 0
    for shift in range(0, 70, 7):
        if position >= len(data):
            raise ProbeError('Truncated protobuf varint')
        byte = data[position]
        position += 1
        if shift == 63 and byte > 1:
            raise ProbeError('Protobuf varint overflow')
        value |= (byte & 0x7f) << shift
        if not byte & 0x80:
            return value, position
    raise ProbeError('Protobuf varint overflow')


def fields(raw: bytes | memoryview):
    """Yield bounded scalar/bytes fields without decoding operation data."""
    data, pos, count = memoryview(raw), 0, 0
    while pos < len(data):
        count += 1
        if count > 1_000_000:
            raise ProbeError('Too many protobuf fields')
        key, pos = _varint(data, pos)
        name, wire = key >> 3, key & 7
        if not name:
            raise ProbeError('Invalid protobuf field number')
        if wire == 0:
            value, pos = _varint(data, pos)
        elif wire in (1, 5):
            size = 8 if wire == 1 else 4
            if pos + size > len(data):
                raise ProbeError('Truncated protobuf fixed field')
            value, pos = data[pos:pos + size], pos + size
        elif wire == 2:
            size, pos = _varint(data, pos)
            if size > len(data) - pos:
                raise ProbeError('Truncated protobuf bytes field')
            value, pos = data[pos:pos + size], pos + size
        else:
            raise ProbeError('Unsupported protobuf wire type')
        yield name, wire, value


def _partition_info(raw):
    size, digest, seen = None, None, set()
    for number, wire, value in fields(raw):
        if number in (1, 2):
            if number in seen or wire != (0 if number == 1 else 2):
                raise ProbeError('Malformed partition size/hash field')
            seen.add(number)
            if number == 1:
                size = value
            else:
                digest = bytes(value)
                if len(digest) != 32:
                    raise ProbeError('Partition digest is not a SHA-256-sized field')
    return size, digest.hex() if digest is not None else None


def parse_manifest(raw: bytes) -> dict:
    # Field numbers from AOSP update_metadata.proto at 4ff049167edfe381966619f3123681f2e6c02138.
    if not raw or len(raw) > MAX_MANIFEST:
        raise ProbeError('Payload manifest is empty or oversized')
    rows, seen, block_size, minor_version = [], set(), 4096, 0
    for number, wire, value in fields(raw):
        if number in (3, 12):
            if number in seen or wire != 0:
                raise ProbeError('Malformed payload scalar')
            seen.add(number)
            if number == 3:
                block_size = value
            else:
                minor_version = value
        if number != 13:
            continue
        if wire != 2 or len(rows) >= 256:
            raise ProbeError('Invalid or excessive payload partition list')
        pname, part, part_seen = None, None, set()
        for field, w, fieldvalue in fields(value):
            if field in (1, 7):
                if field in part_seen or w != 2:
                    raise ProbeError('Malformed or duplicated partition name/info')
                part_seen.add(field)
                if field == 1:
                    try:
                        pname = bytes(fieldvalue).decode('ascii')
                    except UnicodeError as exc:
                        raise ProbeError('Non-ASCII partition name') from exc
                    if not 1 <= len(pname) <= 128:
                        raise ProbeError(f'Invalid partition name length ({len(pname)})')
                    invalid = sorted({ord(char) for char in pname
                                      if not (char.isascii() and (char.isalnum() or char in '_.-'))})
                    if invalid or pname in ('.', '..'):
                        raise ProbeError(f'Invalid partition name character codes: {invalid[:8]}')
                else:
                    part = _partition_info(fieldvalue)
        if pname is None or pname in {row['name'] for row in rows}:
            raise ProbeError('Missing or duplicate partition name')
        rows.append({'name': pname, 'new_size': part[0] if part else None,
                     'declared_new_sha256': part[1] if part else None})
    if not rows:
        raise ProbeError('No payload partitions in the supported manifest')
    return {'block_size': block_size, 'minor_version': minor_version, 'partitions': rows}


def crosscheck_manifest_with_protobuf(raw: bytes, manual: dict) -> None:
    """Independently decode the small inspected subset with the protobuf runtime.

    Unknown fields, including operations, are retained/ignored by protobuf. This
    cross-check does not authenticate the manifest or decode its operations.
    """
    try:
        from google.protobuf import descriptor_pb2, descriptor_pool, message_factory
        from google.protobuf.message import DecodeError
    except ImportError as exc:
        raise ProbeError('Pinned protobuf runtime is unavailable') from exc
    schema = descriptor_pb2.FileDescriptorProto()
    schema.name, schema.package, schema.syntax = 'synthetica_update_subset.proto', 'reference', 'proto2'
    info = schema.message_type.add()
    info.name = 'PartitionInfo'
    update = schema.message_type.add()
    update.name = 'PartitionUpdate'
    manifest = schema.message_type.add()
    manifest.name = 'DeltaArchiveManifest'

    def add(message, name, number, kind, label, *, type_name='', default=''):
        field = message.field.add()
        field.name, field.number, field.type, field.label = name, number, kind, label
        if type_name:
            field.type_name = type_name
        if default:
            field.default_value = default

    field = descriptor_pb2.FieldDescriptorProto
    add(info, 'size', 1, field.TYPE_UINT64, field.LABEL_OPTIONAL)
    add(info, 'hash', 2, field.TYPE_BYTES, field.LABEL_OPTIONAL)
    add(update, 'partition_name', 1, field.TYPE_STRING, field.LABEL_REQUIRED)
    add(update, 'new_partition_info', 7, field.TYPE_MESSAGE, field.LABEL_OPTIONAL,
        type_name='.reference.PartitionInfo')
    add(manifest, 'block_size', 3, field.TYPE_UINT32, field.LABEL_OPTIONAL, default='4096')
    add(manifest, 'minor_version', 12, field.TYPE_UINT32, field.LABEL_OPTIONAL, default='0')
    add(manifest, 'partitions', 13, field.TYPE_MESSAGE, field.LABEL_REPEATED,
        type_name='.reference.PartitionUpdate')
    try:
        pool = descriptor_pool.DescriptorPool()
        pool.Add(schema)
        proto_type = message_factory.MessageFactory(pool).GetPrototype(
            pool.FindMessageTypeByName('reference.DeltaArchiveManifest'))
        decoded = proto_type()
        decoded.ParseFromString(raw)
        if not decoded.IsInitialized():
            raise ProbeError('Protobuf runtime found missing required partition names')
        rows = []
        for partition in decoded.partitions:
            size, digest = None, None
            if partition.HasField('new_partition_info'):
                partinfo = partition.new_partition_info
                size = partinfo.size if partinfo.HasField('size') else None
                digest = bytes(partinfo.hash).hex() if partinfo.HasField('hash') else None
            rows.append({'name': partition.partition_name, 'new_size': size, 'declared_new_sha256': digest})
        independent = {'block_size': decoded.block_size, 'minor_version': decoded.minor_version, 'partitions': rows}
        if manual != independent:
            raise ProbeError('Independent protobuf runtime disagrees with the bounded manifest parser')
    except (DecodeError, ValueError, TypeError, KeyError, IndexError, OverflowError) as exc:
        raise ProbeError('Protobuf runtime could not decode the supported manifest subset') from exc


def _read_small(z, info):
    if info.is_dir() or info.flag_bits & 1 or info.file_size > MAX_SMALL or info.compress_size > MAX_SMALL:
        raise ProbeError(f'Unsafe or oversized metadata member: {info.filename}')
    data = z.read(info)  # validates ZIP CRC at EOF
    if len(data) != info.file_size:
        raise ProbeError('Incomplete metadata member')
    return data


def _payload_offset(z, info):
    if (info.is_dir() or info.flag_bits & 1 or info.compress_type != zipfile.ZIP_STORED
            or info.file_size != info.compress_size):
        raise ProbeError('Payload is not an unencrypted stored ZIP member')
    if info.header_offset < 0 or info.header_offset + LOCAL.size > z.start_dir:
        raise ProbeError('Payload local header is outside ZIP data')
    z.fp.seek(info.header_offset)
    header = z.fp.read(LOCAL.size)
    if len(header) != LOCAL.size:
        raise ProbeError('Truncated payload local header')
    magic, _, flags, method, _, _, _, _, _, namelen, extralen = LOCAL.unpack(header)
    name = z.fp.read(namelen)
    extra = z.fp.read(extralen)
    if (magic != b'PK\x03\x04' or flags != info.flag_bits or method != info.compress_type
            or name != b'payload.bin' or len(extra) != extralen):
        raise ProbeError('Payload local and central ZIP headers differ')
    offset = info.header_offset + LOCAL.size + namelen + extralen
    if offset + info.compress_size > z.start_dir:
        raise ProbeError('Payload extends into the ZIP central directory')
    return offset


def inspect_zip(stream) -> dict:
    with zipfile.ZipFile(stream) as z:
        infos = z.infolist()
        if not 1 <= len(infos) <= 4096:
            raise ProbeError('Unexpected ZIP entry count')
        names = [i.filename for i in infos]
        required = ('META-INF/com/android/metadata', 'payload_properties.txt', 'payload.bin')
        if len(set(names)) != len(names) or not set(required) <= set(names):
            raise ProbeError('Duplicate or missing expected OTA entries')
        legacy = _read_small(z, z.getinfo(required[0]))
        props_raw = _read_small(z, z.getinfo(required[1]))
        try:
            def parse_lines(data):
                result = {}
                for line in data.decode('utf-8').splitlines():
                    key, separator, value = line.partition('=')
                    if not separator or not key or key in result:
                        raise ProbeError('Malformed or duplicate metadata field')
                    result[key] = value
                return result
            metadata, props = parse_lines(legacy), parse_lines(props_raw)
            published = {}
            for field in ('FILE_HASH', 'METADATA_HASH'):
                decoded = base64.b64decode(props[field], validate=True)
                if len(decoded) != 32:
                    raise ProbeError('Payload property is not SHA-256 sized')
                published[field.lower() + '_sha256'] = decoded.hex()
            for field in ('FILE_SIZE', 'METADATA_SIZE'):
                if not re.fullmatch(r'\d{1,20}', props[field]):
                    raise ProbeError('Invalid numeric payload property')
                published[field.lower()] = int(props[field])
        except (UnicodeError, ValueError, KeyError) as exc:
            raise ProbeError('Unsupported OTA metadata/properties') from exc
        payload = z.getinfo('payload.bin')
        offset = _payload_offset(z, payload)
        if published['file_size'] != payload.file_size or payload.file_size < 24:
            raise ProbeError('Advertised payload size does not match the ZIP entry')
        z.fp.seek(offset)
        header = z.fp.read(24)
        if len(header) != 24 or header[:4] != b'CrAU':
            raise ProbeError('Unexpected payload header')
        version, manifest_size, signature_size = struct.unpack('>QQI', header[4:])
        if (version != 2 or not 0 < manifest_size <= MAX_MANIFEST or signature_size > MAX_SIGNATURE
                or 24 + manifest_size + signature_size > payload.file_size):
            raise ProbeError('Unsupported or oversized payload manifest/signature')
        manifest = z.fp.read(manifest_size)
        metadata_signature = z.fp.read(signature_size)
        if len(manifest) != manifest_size or len(metadata_signature) != signature_size:
            raise ProbeError('Truncated payload metadata')
        header_manifest_sha = hashlib.sha256(header + manifest).hexdigest()
        inclusive_sha = hashlib.sha256(header + manifest + metadata_signature).hexdigest()
        parsed = parse_manifest(manifest)
        crosscheck_manifest_with_protobuf(manifest, parsed)
        allowed_metadata = ('ota-type', 'pre-device', 'post-sdk-level', 'post-security-patch-level',
                            'post-build-incremental', 'ota-wipe')
        safe_metadata = {key: metadata[key] for key in allowed_metadata if key in metadata}
        if any(len(value) > 512 for value in safe_metadata.values()):
            raise ProbeError('Unexpectedly long legacy OTA metadata field')
        return {'zip_entry_count': len(infos), 'metadata_fields': safe_metadata,
                'metadata_zip_crc_verified': True, 'payload_properties_zip_crc_verified': True,
                'payload_bytes': payload.file_size, 'payload_header_version': version,
                'manifest_bytes': manifest_size, 'manifest_sha256': hashlib.sha256(manifest).hexdigest(),
                'independent_protobuf_subset_matches': True,
                'metadata_signature_bytes': signature_size, 'advertised_properties': published,
                'advertised_metadata_hash_matches_header_manifest': published['metadata_hash_sha256'] == header_manifest_sha,
                'advertised_metadata_hash_matches_including_signature': published['metadata_hash_sha256'] == inclusive_sha,
                'advertised_metadata_size_matches_header_manifest': published['metadata_size'] == 24 + manifest_size,
                'advertised_metadata_size_matches_including_signature': published['metadata_size'] == 24 + manifest_size + signature_size,
                'manifest': parsed}


def compare_snapshot(manifest: dict) -> list[dict]:
    raw = SNAPSHOT.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SNAPSHOT_SHA256:
        raise ProbeError('Previously measured port snapshot report differs from its pin')
    snapshot = json.loads(raw)
    if snapshot.get('same_super_as_candidate_03_sha256') != '3ae6b934491d3828b43904070a17bab89d56ddf0a79d599b11fd9cb701476673':
        raise ProbeError('Previously measured snapshot does not identify candidate 03 super')
    port = {}
    for group in snapshot['verified_extents_and_super']:
        for name, pair in group['extents'].items():
            if pair['before'] != pair['after'] or name in port:
                raise ProbeError('Port snapshot extents were inconsistent')
            port[name] = pair['before']
    build_raw = BUILD_REPORT.read_bytes()
    if hashlib.sha256(build_raw).hexdigest() != BUILD_REPORT_SHA256:
        raise ProbeError('Candidate 03 build report differs from its pin')
    build = json.loads(build_raw)
    if (build.get('output', {}).get('sha256') != 'bd864ae0d5f5baf26e88f2b5848f15544e4843a46e6ac96636bc25c664e4f425'
            or build.get('status') != 'HOLD_NOT_FLASH_APPROVED'):
        raise ProbeError('Pinned build report does not identify the held candidate 03')
    for member in build['unchanged_members']:
        if member['name'] in ('boot.img', 'dtbo.img'):
            name = member['name'].removesuffix('.img')
            if name in port or member.get('zip_crc_verified_at_eof') is not True:
                raise ProbeError('Candidate image observation was duplicate or CRC-unverified')
            port[name] = {'bytes': member['bytes'], 'sha256': member['sha256']}
    donor = {row['name']: row for row in manifest['partitions']}
    rows = []
    for name in ('system', 'system_ext', 'product', 'vendor', 'boot', 'dtbo'):
        p, d = port[name], donor.get(name)
        if not d or d['new_size'] is None or d['declared_new_sha256'] is None:
            relation = 'not_comparable_manifest_field_absent'
        elif d['new_size'] != p['bytes']:
            relation = 'different_sizes_not_a_whole_partition_match'
        elif d['declared_new_sha256'] != p['sha256']:
            relation = 'same_size_different_declared_hash'
        else:
            relation = 'same_size_and_declared_hash_not_independently_verified'
        rows.append({'partition': name, 'port_observation_kind': 'candidate_03_zip_member' if name in ('boot', 'dtbo') else 'logical_extent',
                     'port_snapshot_bytes': p['bytes'], 'port_snapshot_sha256': p['sha256'],
                     'reference_declared_bytes': d['new_size'] if d else None,
                     'reference_declared_sha256': d['declared_new_sha256'] if d else None,
                     'comparison': relation})
    return rows


def probe() -> dict:
    attempts, remote = [], None
    for url in URLS:
        try:
            remote = HttpRanges(url)
            break
        except ProbeError as exc:
            attempts.append({'host': urllib.parse.urlparse(url).hostname, 'outcome': str(exc)})
    if remote is None:
        raise ProbeError('No catalog CDN supported the bounded range probe: ' + json.dumps(attempts))
    inspected = inspect_zip(RangeReader(remote))
    comparisons = compare_snapshot(inspected['manifest'])
    return {'schema': 'synthetica-madrid-reference-range-probe-v1',
            'status': 'partial_unverified_reference_metadata_only_not_a_rom_or_flash_approval',
            'catalog': CATALOG, 'catalog_md5_claim': 'c38824c8fee14778a5049872f4511d9a',
            'catalog_md5_verified': False, 'url': remote.url, 'remote_bytes': remote.total,
            'http_etag_present': remote.etag is not None, 'http_last_modified_present': remote.modified is not None,
            'range_requests': remote.requests, 'range_bytes': remote.received, 'failed_prior_hosts': attempts,
            'reference': inspected, 'port_partition_comparisons': comparisons,
            'limitations': [
                'Catalog attribution, remote bytes, partition hashes, metadata signature and whole-file MD5 were not independently authenticated.',
                'The declared hashes describe the advertised Madrid target partitions; those images were not downloaded or hashed.',
                'A whole-partition size/hash comparison cannot establish individual file origin, ABI, device compatibility or port source.',
                'This is not a donor for joyeuse, not a build, and not evidence of recovery trust, AVB, runtime, or boot.',
                'No full ROM or partition image was downloaded; no private key, recovery or physical device was accessed or modified.',
            ]}


def main():
    try:
        print(json.dumps(probe(), indent=2, sort_keys=True))
    except (ProbeError, OSError, ValueError, KeyError, zipfile.BadZipFile, NotImplementedError) as exc:
        print(json.dumps({'status': 'inconclusive_no_device_or_provenance_verdict', 'error': str(exc)}, indent=2))
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
