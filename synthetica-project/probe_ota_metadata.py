#!/usr/bin/env python3
"""Inspect only the two pinned OTA metadata entries from candidate 02 part 003.

Not a ZIP extractor: the enclosing part's SHA must be verified by the caller.
The fixed offsets and member hashes came from the previously verified build.
"""
import hashlib
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'third_party/aosp_ota_metadata'))
import ota_metadata_pb2  # noqa: E402

START = 2 * 1_610_612_736
LOCAL = struct.Struct('<4sHHHHHIIIHH')
ENTRIES = (
    (4_712_587_335, 'META-INF/com/android/metadata', 260, 368,
     '70f51292e0858d4f4f23d6d58fc2fb8bf02f9ca86dd6dae13869139492cd228d'),
    (4_712_587_654, 'META-INF/com/android/metadata.pb', 211, 282,
     '3ad45105634884dff53bd7ee250d488552cbeb68f1b2905c2d8aac93fdf3a46e'),
)


def read_entry(f, entry):
    offset, name, compressed, size, expected_hash = entry
    f.seek(offset - START)
    header = f.read(LOCAL.size)
    if len(header) != LOCAL.size:
        raise ValueError('Short ZIP local header')
    fields = LOCAL.unpack(header)
    if (fields[0] != b'PK\x03\x04' or fields[2] != 0 or fields[3] != 8
            or fields[7] != compressed or fields[8] != size):
        raise ValueError('ZIP local header differs from the verified 02 layout')
    if f.read(fields[-2]) != name.encode('ascii'):
        raise ValueError('Unexpected ZIP member name')
    f.seek(fields[-1], 1)
    data = zlib.decompress(f.read(compressed), -15)
    if len(data) != size or hashlib.sha256(data).hexdigest() != expected_hash:
        raise ValueError('Metadata member differs from its verified 02 SHA-256')
    return data


def main(path):
    with open(path, 'rb') as f:
        text, proto = [read_entry(f, entry) for entry in ENTRIES]
    msg = ota_metadata_pb2.OtaMetadata()
    msg.ParseFromString(proto)
    print('Legacy metadata (authenticated by its previously verified member hash):')
    print(text.decode('utf-8'))
    print('Protobuf metadata decoded with pinned AOSP ota_metadata.proto:')
    print(msg)
    print('Property-file values match:', all(
        ('%s=%s' % (key, value)) in text.decode('utf-8').splitlines()
        for key, value in msg.property_files.items()))


if __name__ == '__main__':
    main(sys.argv[1])
