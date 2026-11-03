import hashlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_unversioned_vndk_symbols as probe
import audit_vndk_apex as apex


class MemoryEntry:
    def __init__(self, data):
        self.data = data

    def read_random(self, offset, size):
        return self.data[offset:offset + size]


def as_android_machine(data, machine=183):
    result = bytearray(data)
    struct.pack_into('<H', result, 18, machine)
    return bytes(result)


def capture_provider(collector, data, bits=64, name='libbase.so'):
    entry = MemoryEntry(data)
    collector.capture_provider(entry, len(data), bits, name)


def capture_consumer(collector, data, bits=64):
    entry = MemoryEntry(data)
    parsed = {'class': bits, 'architecture': 'AArch64' if bits == 64 else 'ARM',
              'type': 'dynamic', 'interpreter': '/system/bin/linker64' if bits == 64 else '/system/bin/linker'}
    collector.capture_consumer(entry, len(data), parsed)


def observation(summary, bits, binding, category):
    return next((row for row in summary['observations']
                 if (row['bits'], row['binding'], row['observation']) == (bits, binding, category)), None)


@unittest.skipUnless(probe.versions.ELFFile is not None and shutil.which('gcc'), 'pyelftools and gcc required')
class UnversionedProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / 'base.c').write_text('int provided(void){return 42;}\n')
        (root / 'other.c').write_text('int other_provider(void){return 7;}\n')
        (root / 'consumer.c').write_text(
            'extern int provided(void);\nextern int other_provider(void);\n'
            'extern int weak_optional(void) __attribute__((weak));\n'
            'int main(void){return provided()+other_provider()+(weak_optional?weak_optional():0);}\n')
        (root / 'versions.c').write_text(
            'int versioned_fn(void){return 1;}\nint old_implementation(void){return 2;}\n'
            '__asm__(".symver old_implementation,nondefault_only@ABI_1");\n')
        (root / 'versions.map').write_text('ABI_1 { global: versioned_fn; nondefault_only; local: *; };\n')
        (root / 'versionconsumer.c').write_text(
            'extern int versioned_fn(void); int main(void){return versioned_fn();}\n')
        subprocess.run(['gcc', '-shared', '-fPIC', '-Wl,-soname,libbase.so', '-o', 'libbase.so', 'base.c'], cwd=root, check=True)
        subprocess.run(['gcc', '-shared', '-fPIC', '-Wl,-soname,libother.so', '-o', 'libother.so', 'other.c'], cwd=root, check=True)
        subprocess.run(['gcc', '-Wl,--dynamic-linker,/system/bin/linker64', '-o', 'consumer',
                        'consumer.c', '-L.', '-lbase', '-lother'], cwd=root, check=True)
        subprocess.run(['gcc', '-shared', '-fPIC', '-Wl,-soname,libversioned.so',
                        '-Wl,--version-script=versions.map', '-o', 'libversioned.so', 'versions.c'], cwd=root, check=True)
        subprocess.run(['gcc', '-o', 'versionconsumer', 'versionconsumer.c', '-L.', '-lversioned'], cwd=root, check=True)
        cls.base = as_android_machine((root / 'libbase.so').read_bytes())
        cls.consumer = as_android_machine((root / 'consumer').read_bytes())
        cls.versioned = as_android_machine((root / 'libversioned.so').read_bytes())
        cls.versionconsumer = as_android_machine((root / 'versionconsumer').read_bytes())

        # No host 32-bit runtime is needed: these synthetic fixtures are never run.
        (root / 'start32.c').write_text('extern int provided(void); void _start(void){(void)provided();}\n')
        subprocess.run(['gcc', '-m32', '-nostdlib', '-shared', '-fPIC', '-Wl,-soname,libbase.so',
                        '-o', 'libbase32.so', 'base.c'], cwd=root, check=True)
        subprocess.run(['gcc', '-m32', '-nostdlib', '-pie', '-Wl,-dynamic-linker,/system/bin/linker',
                        '-o', 'consumer32', 'start32.c', '-L.', '-Wl,-l:libbase32.so'], cwd=root, check=True)
        cls.base32 = as_android_machine((root / 'libbase32.so').read_bytes(), 40)
        cls.consumer32 = as_android_machine((root / 'consumer32').read_bytes(), 40)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_strong_weak_and_nonselected_provider_are_separated(self):
        c = probe.Collector()
        capture_provider(c, self.base)
        capture_consumer(c, self.consumer)
        r = c.summarize()
        seen = observation(r, 64, 'strong', 'same_name_seen_in_selected_direct_apex_provider')
        unseen = observation(r, 64, 'strong', 'not_seen_in_selected_direct_apex_providers')
        weak = observation(r, 64, 'weak', 'not_seen_in_selected_direct_apex_providers')
        self.assertEqual((seen['distinct_names'], seen['executable_symbol_edges']), (1, 1))
        self.assertEqual(seen['distinct_names_sha256'], probe._identity({'provided'}))
        # This name is actually provided by an unselected direct dependency:
        # not-seen in the limited set must never be called unresolved.
        self.assertEqual(unseen['distinct_names_sha256'], probe._identity({'other_provider'}))
        self.assertGreaterEqual(weak['distinct_names'], 1)
        self.assertEqual(r['consumer_executable_stats']['parsed_executables'], 1)
        self.assertNotIn('other_provider', str(r))

    def test_incomplete_and_missing_provider_coverage_are_not_complete(self):
        for with_provider in (True, False):
            c = probe.Collector()
            if with_provider:
                capture_provider(c, self.base)
            with mock.patch.object(probe.abi, 'dynamic_needed', return_value=(['libbase.so', 'libbinder.so'], 0)):
                capture_consumer(c, self.consumer)
            r = c.summarize()
            category = ('not_seen_but_selected_provider_coverage_incomplete' if with_provider else
                        'not_compared_no_readable_selected_apex_provider')
            self.assertIsNotNone(observation(r, 64, 'strong', category))
            self.assertIsNone(observation(r, 64, 'strong', 'not_seen_in_selected_direct_apex_providers'))

    def test_versioned_references_are_excluded_but_default_export_is_seen(self):
        refs = probe.undefined_names(self.versionconsumer)
        self.assertNotIn(('versioned_fn', 'strong'), refs['names'])
        self.assertGreaterEqual(refs['counts']['versioned_local_or_hidden_undefined_symbols_excluded'], 1)
        exports = probe.exported_names(self.versioned)
        self.assertIn('versioned_fn', exports['names'])
        self.assertNotIn('nondefault_only', exports['names'])
        self.assertGreaterEqual(exports['counts']['local_or_nondefault_version_definitions_excluded'], 1)

    def test_bitness_must_match_and_synthetic_arm32_is_compared(self):
        c = probe.Collector()
        capture_provider(c, self.base32, 32)
        capture_consumer(c, self.consumer32, 32)
        r = c.summarize()
        seen = observation(r, 32, 'strong', 'same_name_seen_in_selected_direct_apex_provider')
        self.assertEqual(seen['distinct_names_sha256'], probe._identity({'provided'}))
        self.assertIsNone(observation(r, 64, 'strong', 'same_name_seen_in_selected_direct_apex_provider'))
        wrong = probe.Collector()
        capture_provider(wrong, self.base, 32)
        self.assertEqual(next(p for p in wrong.summarize()['selected_apex_providers']
                              if p['bits'] == 32 and p['library'] == 'libbase.so')['status'],
                         'malformed_oversized_or_unreadable')

    def test_bad_and_duplicate_providers_are_handled_without_claims(self):
        c = probe.Collector()
        capture_provider(c, b'not an elf')
        self.assertEqual(next(p for p in c.summarize()['selected_apex_providers']
                              if p['bits'] == 64 and p['library'] == 'libbase.so')['status'],
                         'malformed_oversized_or_unreadable')
        with self.assertRaises(probe.UnversionedProbeError):
            capture_provider(c, self.base)
        with self.assertRaises(probe.UnversionedProbeError):
            probe.undefined_names(b'not an elf')

    def test_digest_is_stable_and_empty_provider_does_not_become_match(self):
        self.assertEqual(probe._identity({'b', 'a'}), hashlib.sha256(b'a\nb\n').hexdigest())
        c = probe.Collector()
        capture_consumer(c, self.consumer)
        r = c.summarize()
        self.assertIsNotNone(observation(r, 64, 'strong', 'not_compared_no_readable_selected_apex_provider'))
        self.assertFalse(r['same_name_by_selected_direct_provider'])

    def test_aggregate_limit_fails_closed(self):
        c = probe.Collector()
        with mock.patch.object(probe, 'MAX_REFERENCE_EDGES', 0):
            with self.assertRaises(probe.UnversionedProbeError):
                capture_consumer(c, self.consumer)

    @unittest.skipUnless(probe.vendor_elf.inventory.pytsk3 is not None and Path('/usr/sbin/mke2fs').is_file(),
                         'pytsk3 and mke2fs required')
    def test_read_only_ext4_scan_delivers_both_callbacks(self):
        with tempfile.TemporaryDirectory(prefix='unversioned-symbol-ext4-') as temp:
            root = Path(temp)
            vendor, payload = root / 'vendor', root / 'payload'
            (vendor / 'bin').mkdir(parents=True)
            (payload / 'lib').mkdir(parents=True)
            (payload / 'lib64').mkdir()
            (vendor / 'bin/consumer').write_bytes(self.consumer)
            (payload / 'lib64/libbase.so').write_bytes(self.base)
            name = b'com.android.vndk.v30'
            manifest = b'\x0a' + bytes([len(name)]) + name + b'\x10\x01'
            (payload / 'apex_manifest.pb').write_bytes(manifest)
            images = []
            for tree in (vendor, payload):
                image = tree.with_suffix('.img')
                with image.open('wb') as f:
                    f.truncate(16 * 1024 * 1024)
                subprocess.run(['/usr/sbin/mke2fs', '-q', '-F', '-t', 'ext4', '-d', str(tree), str(image)],
                               check=True, capture_output=True)
                images.append(image)
            before = [hashlib.sha256(p.read_bytes()).hexdigest() for p in images]
            c = probe.Collector()
            probe.vendor_elf.scan_vendor(images[0], capture=c.capture_consumer)
            _, providers = apex.inspect_ext4_payload(images[1], manifest, provider_observer=c.capture_provider)
            self.assertIn((64, 'libbase.so'), providers)
            r = c.summarize()
            self.assertEqual(r['consumer_executable_stats']['parsed_executables'], 1)
            seen = observation(r, 64, 'strong', 'same_name_seen_in_selected_direct_apex_provider')
            self.assertEqual(seen['distinct_names_sha256'], probe._identity({'provided'}))
            self.assertEqual(before, [hashlib.sha256(p.read_bytes()).hexdigest() for p in images])


if __name__ == '__main__':
    unittest.main()
