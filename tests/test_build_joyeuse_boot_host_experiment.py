import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('joyeuse_boot_host_experiment', ROOT / 'synthetica-project/build_joyeuse_boot_host_experiment.py')
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)


def fixture(command=b'console=ttyMSM0 androidboot.selinux=permissive'):
    page = 4096
    image = bytearray(page * 4)
    image[:8] = b'ANDROID!'
    struct.pack_into('<10I', image, 8, 17, 0x8000, 19, 0x1000000, 0, 0, 0x100, page, 2, 0)
    image[64:64+len(command)] = command
    struct.pack_into('<I', image, 1644, 1660)
    struct.pack_into('<I', image, 1648, 21)
    struct.pack_into('<Q', image, 1652, 0x1f00000)
    image[4096:4096+17] = b'K'*17
    image[8192:8192+19] = b'R'*19
    image[12288:12288+21] = b'D'*21
    image[576:608] = boot.boot_id(b'K'*17, b'R'*19, b'D'*21)
    return bytes(image)


class HostBootExperimentTests(unittest.TestCase):
    def test_construct_keeps_parts_and_requests_enforcing_only(self):
        source = fixture(); kernel = b'new kernel' * 500
        result, report = boot.construct(source, kernel)
        parts, fields = boot.parse(result)
        self.assertEqual(parts, {'kernel': kernel, 'ramdisk': b'R'*19, 'dtb': b'D'*21})
        self.assertEqual(b''.join(fields), b'console=ttyMSM0 androidboot.selinux=enforcing')
        old, new = bytearray(source[:4096]), bytearray(result[:4096])
        for start, end in ((8, 12), (64, 576), (576, 608), (608, 1632)):
            new[start:end] = old[start:end]
        self.assertEqual(new, old)
        self.assertEqual(report['ramdisk_sha256'], hashlib.sha256(b'R'*19).hexdigest())
        self.assertEqual(report['dtb_sha256'], hashlib.sha256(b'D'*21).hexdigest())
        self.assertNotEqual(result[576:596], source[576:596])

    def test_requires_one_unambiguous_permissive_token(self):
        for cmd in (b'console=x', b'androidboot.selinux=enforcing',
                    b'androidboot.selinux=permissive androidboot.selinux=permissive',
                    b'androidboot.selinux=permissive androidboot.selinux=enforcing',
                    b'fooandroidboot.selinux=permissive'):
            with self.subTest(cmd=cmd), self.assertRaises(ValueError):
                boot.construct(fixture(cmd), b'new')

    def test_rejects_corrupt_components_header_and_padding(self):
        for offset in (576, 1700, 4096, 4113, 8192, 12288):
            source = bytearray(fixture()); source[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                boot.construct(bytes(source), b'new')
        for source in (fixture()[:-1], fixture() + b'\0'*4096):
            with self.assertRaises(ValueError): boot.construct(source, b'new')
        with self.assertRaises(ValueError): boot.construct(fixture(), b'')

    def test_rejects_bad_cstring_and_nonzero_recovery(self):
        for offset in (100, 1632, 1636):
            source = bytearray(fixture()); source[offset] = 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                boot.construct(bytes(source), b'new')

    def test_read_locked_rejects_symlink_wrong_hash_and_wrong_size(self):
        with tempfile.TemporaryDirectory() as td:
            source = Path(td)/'source'; source.write_bytes(b'abc')
            expected = hashlib.sha256(b'abc').hexdigest()
            self.assertEqual(boot.read_locked(source, 3, expected), b'abc')
            with self.assertRaises(ValueError): boot.read_locked(source, 3, '0'*64)
            with self.assertRaises(ValueError): boot.read_locked(source, 2, expected)
            link = Path(td)/'link'; link.symlink_to(source)
            with self.assertRaises(OSError): boot.read_locked(link, 3, expected)

    def test_exclusive_write_and_output_guard(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td)/'out'; boot.write_exclusive(path, b'first')
            with self.assertRaises(FileExistsError): boot.write_exclusive(path, b'second')
            self.assertEqual(path.read_bytes(), b'first')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(ValueError):
                boot.build(Path('missing'), Path('missing'), Path('missing'), Path('missing'), Path(td)/'NOT-FOR-FLASH')
            with self.assertRaises(ValueError):
                boot.build(Path('missing'), Path('missing'), Path('missing'), Path('missing'), Path(td))


if __name__ == '__main__': unittest.main()
