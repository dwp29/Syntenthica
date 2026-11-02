import hashlib
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
import audit_vendor_elf_metadata as audit
import audit_vintf_candidate as inventory


class Buffer:
    def __init__(self, data):
        self.data = data

    def read_random(self, offset, length):
        return self.data[offset:offset + length]


def fake_elf(bits, machine, interpreter):
    ident = b'\x7fELF' + bytes([1 if bits == 32 else 2, 1, 1]) + b'\0' * 9
    string = interpreter.encode('ascii') + b'\0'
    if bits == 32:
        size, phsize = 52, 32
        header = struct.pack('<16sHHIIIIIHHHHHH', ident, 3, machine, 1, 0, size, 0, 0,
                             size, phsize, 1, 0, 0, 0)
        program = struct.pack('<IIIIIIII', 3, size + phsize, 0, 0, len(string), len(string), 0, 1)
    else:
        size, phsize = 64, 56
        header = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, machine, 1, 0, size, 0, 0,
                             size, phsize, 1, 0, 0, 0)
        program = struct.pack('<IIQQQQQQ', 3, 0, size + phsize, 0, 0, len(string), len(string), 1)
    return header + program + string


class ElfMetadataTests(unittest.TestCase):
    def test_both_arm_classes_and_known_interpreters(self):
        for bits, machine, path in ((32, 40, '/system/bin/linker'),
                                    (64, 183, '/system/bin/linker64')):
            data = fake_elf(bits, machine, path)
            result = audit.classify_elf(Buffer(data), len(data))
            self.assertEqual(result['class'], bits)
            self.assertEqual(result['architecture'], 'ARM' if bits == 32 else 'AArch64')
            self.assertEqual(result['interpreter'], path)
            self.assertEqual(result['type'], 'dynamic')

    def test_non_elf_unknown_interpreter_and_corrupt_are_distinct(self):
        self.assertIsNone(audit.classify_elf(Buffer(b'text'), 4))
        other = fake_elf(64, 183, '/unpublished/private')
        self.assertEqual(audit.classify_elf(Buffer(other), len(other))['interpreter'], 'other_absolute_path')
        self.assertNotIn('/unpublished/private', str(audit.classify_elf(Buffer(other), len(other))))
        truncated = fake_elf(32, 40, '/system/bin/linker')[:-3]
        with self.assertRaises(audit.ElfMetadataError):
            audit.classify_elf(Buffer(truncated), len(truncated))
        with self.assertRaises(audit.ElfMetadataError):
            audit.classify_elf(Buffer(b'\x7fELF'), 4)
        wrong_endian = bytearray(fake_elf(32, 40, '/system/bin/linker'))
        wrong_endian[5] = 2
        with self.assertRaises(audit.ElfMetadataError):
            audit.classify_elf(Buffer(wrong_endian), len(wrong_endian))

    def test_program_header_limit_is_enforced(self):
        malicious = bytearray(fake_elf(64, 183, '/system/bin/linker64'))
        struct.pack_into('<H', malicious, 56, audit.MAX_PHNUM + 1)
        with self.assertRaises(audit.ElfMetadataError):
            audit.classify_elf(Buffer(malicious), len(malicious))

    @unittest.skipUnless(inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs are required')
    def test_synthetic_ext4_scans_are_bounded_and_unchanged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            vendor, system = root / 'vendor', root / 'system'
            (vendor / 'bin/hw').mkdir(parents=True)
            (system / 'system/bin').mkdir(parents=True)
            (system / 'system/apex').mkdir(parents=True)
            (vendor / 'bin/hw/arm32').write_bytes(fake_elf(32, 40, '/system/bin/linker'))
            (vendor / 'bin/arm64').write_bytes(fake_elf(64, 183, '/system/bin/linker64'))
            (vendor / 'bin/script').write_text('not ELF')
            os.symlink('/bin/arm64', vendor / 'bin/link-skip')
            os.symlink('/apex/com.android.runtime/bin/linker', system / 'system/bin/linker')
            (system / 'system/bin/linker64').write_bytes(fake_elf(64, 183, '/system/bin/linker64'))
            (system / 'system/apex/com.android.runtime.apex').write_bytes(b'not a real package')
            images = {}
            for name, tree in (('vendor', vendor), ('system', system)):
                image = root / (name + '.img')
                with image.open('wb') as f:
                    f.truncate(16 * 1024**2)
                subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(tree), str(image)],
                               check=True)
                images[name] = image
            before = {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in images.items()}
            v = audit.scan_vendor(images['vendor'])
            s = audit.scan_system(images['system'])
            self.assertEqual(v['regular_files'], 3)
            self.assertEqual(v['symlinks_not_followed'], 1)
            self.assertEqual(v['non_elf_files'], 1)
            self.assertEqual(sum(x['count'] for x in v['elf_categories']), 2)
            self.assertEqual(s['system_linker_paths'][0]['status'], 'symlink_not_followed')
            self.assertEqual(s['system_linker_paths'][0]['target'], '/apex/com.android.runtime/bin/linker')
            self.assertEqual(s['system_linker_paths'][1]['elf']['architecture'], 'AArch64')
            self.assertEqual(s['runtime_apex_candidates']['candidates'][0]['name'], 'com.android.runtime.apex')
            self.assertEqual(before, {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in images.items()})


if __name__ == '__main__':
    unittest.main()
