#!/usr/bin/env python3
"""Plan one bounded product extension inside a raw super image, without moving other partitions.

The source must have identical valid geometry and slot copies, one distinct
linear extent per partition, one block device, canonical non-overlapping table
layout, and enough aligned free space *after* all existing extents. A single
additional linear product extent is inserted; all four metadata checksums and
copies are regenerated. This is a host-only planner, not a device measurement or
proof of flash safety. An independent liblp/lpdump check is also required by the
build workflow before an image is retained.
"""
from __future__ import annotations
import hashlib
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'research/hyperos4'))
import lp_metadata as lp

class LPExpandError(RuntimeError):
    pass


def round_up(n: int, alignment: int) -> int:
    if n < 0 or alignment <= 0:
        raise LPExpandError('Invalid alignment')
    return ((n + alignment - 1) // alignment) * alignment


def _row_name(data: bytes) -> str:
    return lp._named(data[:36], 'partition')


def build(prefix: bytes, image_bytes: int, growth: int, *, expected_metadata_sha: str | None = None) -> tuple[bytes, dict]:
    if (not isinstance(prefix, bytes) or not 0 < len(prefix) <= lp.MAX_PREFIX
            or type(image_bytes) is not int or image_bytes <= 0
            or type(growth) is not int or growth <= 0 or growth > 64 * 1024 * 1024
            or growth % 4096):
        raise LPExpandError('Invalid prefix, image size or product growth')
    layout = lp.inspect_raw_super(prefix, image_bytes)
    geo = layout['geometry_primary']
    slots = layout['metadata_slots']
    if layout['geometry_copies_match'] is not True or not slots or any(s['copies_match'] is not True for s in slots):
        raise LPExpandError('Geometry or metadata copies differ or are invalid')
    base = slots[0]['primary']
    metadata_sha = base.get('header_and_tables_sha256')
    if (any(s['primary'].get('header_and_tables_sha256') != metadata_sha for s in slots)
            or (expected_metadata_sha is not None and metadata_sha != expected_metadata_sha)):
        raise LPExpandError('Metadata slots do not match the locked source')
    if len(base['block_devices']) != 1:
        raise LPExpandError('Expected exactly one super block device')
    device = base['block_devices'][0]
    alignment = device['alignment_bytes'] or geo['logical_block_bytes']
    if (device['name'] != 'super' or device['size_bytes_declared'] != image_bytes
            or device['alignment_offset_bytes'] != 0 or alignment % geo['logical_block_bytes']
            or growth % geo['logical_block_bytes'] or growth % alignment):
        raise LPExpandError('Unsupported super block device or alignment')
    allocated = geo['metadata_max_bytes']
    slot_count = geo['slot_count']
    metadata_end = lp.METADATA_START + 2 * allocated * slot_count
    if metadata_end > len(prefix) or metadata_end > device['first_sector'] * lp.SECTOR_BYTES:
        raise LPExpandError('Metadata reserved area is outside the prefix or overlaps data')
    entries = base['partitions']
    if not entries or len({p['name'] for p in entries}) != len(entries):
        raise LPExpandError('Missing or duplicate logical partitions')
    groups = {g['name']: g for g in base['groups']}
    physical = []
    for p in entries:
        e = p.get('first_extent') or {}
        if (p.get('extent_count') != 1 or e.get('type') != 0 or e.get('source_index') != 0
                or e.get('sectors', 0) <= 0 or p['group'] not in groups):
            raise LPExpandError('Only single, nonempty linear source extents are supported')
        start = e['target_sector'] * lp.SECTOR_BYTES
        end = start + p['bytes']
        if (start < device['first_sector'] * lp.SECTOR_BYTES or end > image_bytes
                or start % geo['logical_block_bytes'] or p['bytes'] % geo['logical_block_bytes']):
            raise LPExpandError('Existing extent is out of bounds or misaligned')
        physical.append({'name': p['name'], 'start': start, 'end': end, 'bytes': p['bytes'],
                         'group': p['group'], 'attributes': p['attributes']})
    ordered = sorted(physical, key=lambda x: x['start'])
    if any(a['end'] > b['start'] for a, b in zip(ordered, ordered[1:])):
        raise LPExpandError('Source partitions overlap')
    product = next((p for p in physical if p['name'] == 'product'), None)
    if product is None:
        raise LPExpandError('Product partition is missing')
    tail_start = round_up(max(x['end'] for x in physical), alignment)
    tail_end = tail_start + growth
    if tail_start < product['end'] or tail_end > image_bytes:
        raise LPExpandError('No sufficiently large aligned trailing free extent')
    group_usage = sum(p['bytes'] for p in physical if p['group'] == product['group'])
    maximum = groups[product['group']]['maximum_bytes']
    if maximum and group_usage + growth > maximum:
        raise LPExpandError('Product growth would exceed the logical-partition group maximum')

    first_offset = lp.METADATA_START
    header_size = struct.unpack_from('<I', prefix, first_offset + 8)[0]
    tables_size = struct.unpack_from('<I', prefix, first_offset + 44)[0]
    header = bytearray(prefix[first_offset:first_offset + header_size])
    tables = prefix[first_offset + header_size:first_offset + header_size + tables_size]
    desc = [struct.unpack_from('<III', header, o) for o in (80, 92, 104, 116)]
    (p_start, p_count, p_size), (e_start, e_count, e_size), (g_start, g_count, g_size), (d_start, d_count, d_size) = desc
    if (p_start != 0 or p_size != 52 or e_size != 24 or g_size != 48 or d_size != 64
            or e_start != p_count * p_size or g_start != e_start + e_count * e_size
            or d_start != g_start + g_count * g_size or d_start + d_count * d_size != tables_size
            or p_count != len(entries) or e_count != p_count or d_count != 1):
        raise LPExpandError('Metadata table is not the supported compact canonical layout')
    partitions = [bytearray(tables[p_start + i*p_size:p_start + (i+1)*p_size]) for i in range(p_count)]
    extent_rows = [tables[e_start + i*e_size:e_start + (i+1)*e_size] for i in range(e_count)]
    indices = []
    product_index = None
    for row in partitions:
        name = _row_name(row)
        first, count = struct.unpack_from('<II', row, 40)
        if count != 1 or first >= e_count:
            raise LPExpandError('Source partition extent references are unsupported')
        indices.append(first)
        if name == 'product':
            if product_index is not None:
                raise LPExpandError('Duplicate product partition')
            product_index = first
    if sorted(indices) != list(range(e_count)) or product_index is None:
        raise LPExpandError('Source extents are shared, missing, or unreferenced')
    for row in partitions:
        first = struct.unpack_from('<I', row, 40)[0]
        if _row_name(row) == 'product':
            struct.pack_into('<I', row, 44, 2)
        elif first > product_index:
            struct.pack_into('<I', row, 40, first + 1)
    added = struct.pack('<QIQI', growth // lp.SECTOR_BYTES, 0, tail_start // lp.SECTOR_BYTES, 0)
    extent_rows.insert(product_index + 1, added)
    new_tables = b''.join(bytes(r) for r in partitions) + b''.join(extent_rows) + tables[g_start:d_start] + tables[d_start:]
    if len(new_tables) != tables_size + e_size or header_size + len(new_tables) > allocated:
        raise LPExpandError('Expanded metadata exceeds its reserved allocation')
    struct.pack_into('<I', header, 44, len(new_tables))
    struct.pack_into('<I', header, 96, e_count + 1)
    struct.pack_into('<I', header, 104, g_start + e_size)
    struct.pack_into('<I', header, 116, d_start + e_size)
    header[48:80] = hashlib.sha256(new_tables).digest()
    header[12:44] = b'\0' * 32
    header[12:44] = hashlib.sha256(header).digest()
    blob = bytes(header) + new_tables
    out = bytearray(prefix)
    regions = []
    for slot in range(slot_count):
        for offset in (lp.METADATA_START + allocated * slot,
                       lp.METADATA_START + allocated * slot_count + allocated * slot):
            original_blob = prefix[offset:offset + header_size + tables_size]
            if original_blob != prefix[first_offset:first_offset + header_size + tables_size]:
                raise LPExpandError('Metadata copy differs from the first slot')
            if any(prefix[offset + header_size + tables_size:offset + len(blob)]):
                raise LPExpandError('Metadata insertion would overwrite nonzero slot padding')
            out[offset:offset + len(blob)] = blob
            regions.append({'start': offset, 'end': offset + len(blob)})
    rebuilt = lp.inspect_raw_super(bytes(out), image_bytes)
    if rebuilt['geometry_copies_match'] is not True or any(s['copies_match'] is not True for s in rebuilt['metadata_slots']):
        raise LPExpandError('Rebuilt metadata failed checksums or copy consistency')
    new_parts = {p['name']: p for p in rebuilt['metadata_slots'][0]['primary']['partitions']}
    old_parts = {p['name']: p for p in entries}
    if set(new_parts) != set(old_parts):
        raise LPExpandError('Partition names changed during growth')
    for name, old in old_parts.items():
        expected = dict(old)
        if name == 'product':
            expected['extent_count'] = 2
            expected['bytes'] += growth
        if new_parts[name] != expected:
            raise LPExpandError('Unexpected metadata change for partition ' + name)
    if (rebuilt['metadata_slots'][0]['primary']['groups'] != base['groups']
            or rebuilt['metadata_slots'][0]['primary']['block_devices'] != base['block_devices']):
        raise LPExpandError('Group or block-device metadata changed')
    return bytes(out), {'source_metadata_sha256': metadata_sha,
                        'output_metadata_sha256': rebuilt['metadata_slots'][0]['primary']['header_and_tables_sha256'],
                        'metadata_slots': slot_count, 'metadata_regions': regions,
                        'metadata_reserved_end': metadata_end, 'alignment_bytes': alignment,
                        'product_original': product, 'product_new_extent': {'start': tail_start, 'end': tail_end,
                                                                            'bytes': growth, 'source_offset': product['bytes']},
                        'product_bytes_after': product['bytes'] + growth,
                        'physical_super_bytes': image_bytes, 'group': product['group'],
                        'group_original_bytes': group_usage, 'group_maximum_bytes': maximum,
                        'other_partitions': [p for p in physical if p['name'] != 'product'],
                        'limitations': ['On-disk metadata is not a measurement of the real device.',
                                        'Checksums and a liblp host read do not prove AVB, recovery or boot compatibility.']}
