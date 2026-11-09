"""Offline installer integration with the SHA-pinned public ROM boot image.

ARM tools execute through QEMU on a regular file in a temporary directory.
The harness redirects paths and denies writing to real block devices. This does
not run recovery, verify the bootloader's AVB chain, or boot the result.
"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import hashlib
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'build-kit/scripts'))
import audit_synthetica3_boot as boot
import audit_boot_avb_hash as avb

spec = importlib.util.spec_from_file_location('installer_fixture', ROOT / 'tests/test_synthetica3_installer20_qemu.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)

PUBLIC_BOOT_SHA = 'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f'
IMAGE_SHA = '650d5f1e9e73788babeb67e5a21a30e565babd059f8cd908c318531464a74287'
fixture.IMAGE_SHA = IMAGE_SHA

def cpio_inventory(data):
    """Bounded newc inventory without extracting files or following symlinks."""
    pos, entries = 0, {}
    while True:
        if pos + 110 > len(data) or data[pos:pos+6] not in (b'070701', b'070702'):
            raise ValueError('invalid newc header')
        h = [int(data[pos+6+i*8:pos+14+i*8], 16) for i in range(13)]
        pos += 110
        mode, uid, gid, nlink, mtime, size, namesize = h[1], h[2], h[3], h[4], h[5], h[6], h[11]
        if not 1 <= namesize <= 4096 or pos + namesize > len(data):
            raise ValueError('invalid newc name')
        name = data[pos:pos+namesize]
        if not name.endswith(b'\0'): raise ValueError('unterminated name')
        name = name[:-1].decode('utf-8', 'strict')
        pos = (pos + namesize + 3) & ~3
        if pos + size > len(data): raise ValueError('truncated newc data')
        body = data[pos:pos+size]
        pos = (pos + size + 3) & ~3
        if name == 'TRAILER!!!': return entries
        if name in entries: raise ValueError('duplicate newc name')
        entries[name] = {'mode': mode, 'uid': uid, 'gid': gid, 'nlink': nlink,
                         'mtime': mtime, 'size': size, 'sha256': hashlib.sha256(body).hexdigest()}


def avb_descriptor_size(image, report):
    with image.open('rb') as f:
        footer = report['avb']; f.seek(footer['vbmeta_offset']); vb = f.read(footer['vbmeta_bytes'])
    header = avb.HEADER.unpack_from(vb)
    auth, off, length = header[3], header[14], header[15]
    desc = vb[256+auth+off:256+auth+off+length]
    tag, following, image_size, algorithm, namelen, saltlen, digestlen, flags, reserved = avb.HASH_DESC.unpack_from(desc)
    if tag != 2 or desc[avb.HASH_DESC.size:avb.HASH_DESC.size+namelen] != b'boot':
        raise ValueError('unexpected AVB descriptor')
    algo = algorithm.rstrip(b'\0').decode('ascii')
    start = avb.HASH_DESC.size + namelen
    salt = desc[start:start+saltlen]
    expected = desc[start+saltlen:start+saltlen+digestlen]
    if algo not in ('sha256','sha512') or digestlen != hashlib.new(algo).digest_size:
        raise ValueError('unexpected AVB hash algorithm')
    digest = hashlib.new(algo); digest.update(salt)
    with image.open('rb') as f:
        remaining = image_size
        while remaining:
            block = f.read(min(1048576, remaining))
            if not block: raise ValueError('descriptor exceeds file')
            digest.update(block); remaining -= len(block)
    return {'descriptor_image_size': image_size, 'footer_original_image_size': footer['original_image_size'],
            'raw_descriptor_hash_matches': digest.digest() == expected, 'algorithm_type': header[5]}

@unittest.skipUnless(os.environ.get('S31_INFINITY_OFFLINE') == '1', 'public ROM and QEMU test opt-in')
class PublicROMInstallerTest(unittest.TestCase):
    setUp = fixture.OriginalAnyKernelTests.setUp
    run_entry = fixture.OriginalAnyKernelTests.run_entry

    def test_actual_installer_on_pinned_public_boot_regular_file(self):
        source = Path(os.environ['S31_PUBLIC_BOOT'])
        self.assertEqual(source.stat().st_size, 134217728)
        self.assertEqual(fixture.sha(source.read_bytes()), PUBLIC_BOOT_SHA)
        before = boot.inspect_boot(source)
        shutil.copyfile(source, self.boot)
        p = self.run_entry()
        self.assertEqual(p.returncode, 0, p.stdout[-8000:])
        self.assertIn('Done. No automatic reboot.', p.stdout)
        after = boot.inspect_boot(self.boot)
        comparison = boot.compare_boot(before, after, IMAGE_SHA)
        inventories = []
        for i, (path, report) in enumerate(((source, before), (self.boot, after))):
            sec = report['sections']['ramdisk']
            packed = self.root / f'ramdisk-{i}.packed'
            unpacked = self.root / f'ramdisk-{i}.cpio'
            with path.open('rb') as f:
                f.seek(sec['offset']); packed.write_bytes(f.read(sec['bytes']))
            subprocess.run(['qemu-arm-static', str(self.arm / 'magiskboot'), 'decompress', str(packed), str(unpacked)],
                           check=True, capture_output=True)
            if unpacked.stat().st_size > 100000000: raise ValueError('ramdisk too large')
            inventories.append(cpio_inventory(unpacked.read_bytes()))
        old, new = inventories
        differences = {name: {'original': old.get(name), 'output': new.get(name)}
                       for name in sorted(old.keys() | new.keys()) if old.get(name) != new.get(name)}
        result = {'scope': 'Emulated installer on public ROM regular file, no recovery or physical boot; external AVB not verified.',
                  'installer_completed': True, 'boot_comparison': comparison,
                  'ramdisk_formats': [before['ramdisk_format_guess'], after['ramdisk_format_guess']],
                  'ramdisk_entry_counts': [len(old), len(new)],
                  'ramdisk_changed_entries': sorted(differences),
                  'ramdisk_content_changes': sorted(name for name in old.keys() | new.keys()
                    if name != '.' and (name not in old or name not in new or old[name]['sha256'] != new[name]['sha256'])),
                  'ramdisk_mode_changes': sorted(name for name in old.keys() & new.keys() if old[name]['mode'] != new[name]['mode']),
                  'ramdisk_uid_gid_changes': sorted(name for name in old.keys() & new.keys() if (old[name]['uid'],old[name]['gid']) != (new[name]['uid'],new[name]['gid'])),
                  'harness_euid': os.geteuid(),
                  'input_avb_sizes': avb_descriptor_size(source, before), 'output_avb_sizes': avb_descriptor_size(self.boot, after)}
        try:
            result['output_embedded_avb'] = avb.inspect(self.boot)
        except (ValueError, OSError) as e:
            result['output_embedded_avb'] = {'read_error': str(e)}
        print('INFINITY_OFFLINE_RESULT=' + json.dumps(result, sort_keys=True))
        self.assertTrue(comparison['candidate_kernel_equals_bundle_image'])
        self.assertTrue(all(comparison['stable_header_fields_match'].values()))
        self.assertTrue(all(value for name, value in comparison['non_kernel_sections_match'].items() if name != 'ramdisk'))
        self.assertEqual(result['ramdisk_content_changes'], [], 'ramdisk contents changed')
        self.assertEqual(result['ramdisk_mode_changes'], [], 'ramdisk mode changed')
        self.assertTrue(result['input_avb_sizes']['raw_descriptor_hash_matches'])
        self.assertFalse(result['output_avb_sizes']['raw_descriptor_hash_matches'])
        self.assertTrue(comparison['candidate_legacy_boot_id_matches'])

if __name__ == '__main__':
    unittest.main()
