import hashlib
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
from test_audit_vendor_elf_metadata import Buffer
import audit_vendor_abi as audit
import audit_vendor_elf_metadata as elf
import audit_vintf_candidate as inventory


def dynamic_elf(bits: int, names: list[str]) -> bytes:
    ident = b'\x7fELF' + bytes([1 if bits == 32 else 2, 1, 1]) + b'\0' * 9
    hsize, phsize, dfmt = (52, 32, '<iI') if bits == 32 else (64, 56, '<qQ')
    phcount, dynsize = 3, struct.calcsize(dfmt) * (len(names) + 3)
    dynoff = hsize + phcount * phsize
    strdata, indices = bytearray(b'\0'), []
    for name in names:
        indices.append(len(strdata))
        strdata.extend(name.encode() + b'\0')
    stroff = dynoff + dynsize
    interp = ('/system/bin/linker' if bits == 32 else '/system/bin/linker64').encode() + b'\0'
    interpoff = stroff + len(strdata)
    total, base = interpoff + len(interp), 0x1000
    if bits == 32:
        header = struct.pack('<16sHHIIIIIHHHHHH', ident, 3, 40, 1, 0, hsize, 0, 0,
                             hsize, phsize, phcount, 0, 0, 0)
        load = struct.pack('<IIIIIIII', 1, 0, base, 0, total, total, 0, 0x1000)
        dyn = struct.pack('<IIIIIIII', 2, dynoff, base + dynoff, 0, dynsize, dynsize, 0, 4)
        iph = struct.pack('<IIIIIIII', 3, interpoff, base + interpoff, 0, len(interp), len(interp), 0, 1)
    else:
        header = struct.pack('<16sHHIQQQIHHHHHH', ident, 3, 183, 1, 0, hsize, 0, 0,
                             hsize, phsize, phcount, 0, 0, 0)
        load = struct.pack('<IIQQQQQQ', 1, 0, 0, base, 0, total, total, 0x1000)
        dyn = struct.pack('<IIQQQQQQ', 2, 0, dynoff, base + dynoff, 0, dynsize, dynsize, 8)
        iph = struct.pack('<IIQQQQQQ', 3, 0, interpoff, base + interpoff, 0, len(interp), len(interp), 1)
    tags = [(5, base + stroff), (10, len(strdata))] + [(1, n) for n in indices] + [(0, 0)]
    return header + load + dyn + iph + b''.join(struct.pack(dfmt, *pair) for pair in tags) + bytes(strdata) + interp


class AbiTests(unittest.TestCase):
    def test_parses_both_classes_and_deduplicates_dependencies(self):
        for bits in (32, 64):
            data = dynamic_elf(bits, ['liba.so', 'libb.so', 'liba.so'])
            names, invalid = audit.dynamic_needed(Buffer(data), len(data))
            self.assertEqual(names, ['liba.so', 'libb.so'])
            self.assertEqual(invalid, 0)
            self.assertEqual(elf.classify_elf(Buffer(data), len(data))['class'], bits)

    @unittest.skipUnless(Path('/usr/bin/true').is_file() and shutil.which('readelf'), 'Host ELF and readelf required')
    def test_host_elf_names_match_readelf_without_running_it(self):
        path = Path('/usr/bin/true')
        data = path.read_bytes()
        reference = subprocess.run(['readelf', '-d', str(path)], capture_output=True, text=True, check=True)
        expected = sorted(set(re.findall(r'\(NEEDED\).*?\[([^\]]+)\]', reference.stdout)))
        names, invalid = audit.dynamic_needed(Buffer(data), len(data))
        self.assertEqual(names, expected)
        self.assertEqual(invalid, 0)

    def test_invalid_library_name_is_not_exposed(self):
        data = dynamic_elf(64, ['../private.so', 'libgood.so'])
        names, invalid = audit.dynamic_needed(Buffer(data), len(data))
        self.assertEqual(names, ['libgood.so'])
        self.assertEqual(invalid, 1)
        self.assertNotIn('private', str(names))

    def test_bad_dynamic_offsets_and_truncated_input_fail_closed(self):
        data = dynamic_elf(64, ['libc.so'])
        broken = bytearray(data)
        struct.pack_into('<Q', broken, 64 + 56 + 8, len(data) + 100)
        with self.assertRaises((audit.AbiAuditError, elf.ElfMetadataError)):
            audit.dynamic_needed(Buffer(broken), len(broken))
        with self.assertRaises((audit.AbiAuditError, elf.ElfMetadataError)):
            audit.dynamic_needed(Buffer(data[:-3]), len(data) - 3)

    def test_summary_never_treats_name_match_as_compatibility(self):
        collector = audit.Collector()
        collector.references[(64, 'libmissing.so')] = 3
        collector.providers[(64, 'libx.so')]['symlink_not_followed'].add('vendor')
        collector.references[(64, 'libx.so')] = 2
        result = collector.summarize()
        categories = result['needed_name_pair_categories']
        self.assertEqual(categories['not_seen_in_selected_library_roots']['unique_bitness_name_pairs'], 1)
        self.assertEqual(categories['only_symlink_name_seen_unresolved']['unique_bitness_name_pairs'], 1)
        self.assertNotIn('compatible', categories)
        self.assertTrue(any('do not prove' in x for x in result['limitations']))

    @unittest.skipUnless(inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs are required')
    def test_ext4_vendor_references_and_library_roots_are_read_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trees = {part: root / part for part in ('system', 'system_ext', 'vendor', 'product')}
            for path in trees.values():
                path.mkdir()
            (trees['vendor'] / 'bin').mkdir()
            (trees['vendor'] / 'lib').mkdir()
            (trees['vendor'] / 'bin/a').write_bytes(dynamic_elf(32, ['libgood.so', 'liblink.so', 'libunseen.so']))
            (trees['vendor'] / 'lib/libgood.so').write_bytes(dynamic_elf(32, []))
            os.symlink('/not-followed', trees['vendor'] / 'lib/liblink.so')
            images = {}
            for part, tree in trees.items():
                image = root / (part + '.img')
                with image.open('wb') as f:
                    f.truncate(16 * 1024**2)
                subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(tree), str(image)],
                               check=True)
                images[part] = image
            before = {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in images.items()}
            collector = audit.Collector()
            for part, image in images.items():
                collector.scan_library_roots(image, part)
            elf.scan_vendor(images['vendor'], capture=collector.capture_vendor_file)
            result = collector.summarize()
            self.assertEqual(result['vendor_dynamic_executable_counts']['parsed_vendor_executables'], 1)
            categories = result['needed_name_pair_categories']
            self.assertEqual(categories['matching_name_and_basic_elf_header_seen']['unique_bitness_name_pairs'], 1)
            self.assertEqual(categories['only_symlink_name_seen_unresolved']['unique_bitness_name_pairs'], 1)
            self.assertEqual(categories['not_seen_in_selected_library_roots']['unique_bitness_name_pairs'], 1)
            self.assertEqual(before, {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in images.items()})


if __name__ == '__main__':
    unittest.main()
