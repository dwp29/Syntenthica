"""Synthetic ELF version-table tests; executables are compiled but never run."""
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'synthetica-project'))
import audit_vndk_symbols as audit


def fake_entry(data):
    return SimpleNamespace(read_random=lambda offset, size: data[offset:offset + size])


@unittest.skipUnless(audit.ELFFile and shutil.which('gcc'), 'pyelftools and gcc required for synthetic ELF fixture')
class SymbolVersionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='synthetic-vndk-symbols-')
        cls.root = Path(cls.temp.name)
        (cls.root / 'good.c').write_text('int present(void) { return 42; }\n')
        (cls.root / 'wrong.c').write_text('int different(void) { return 12; }\n')
        (cls.root / 'version.map').write_text('ABI_1 { global: present; different; local: *; };\n')
        (cls.root / 'main.c').write_text('extern int present(void); int main(void) { return present(); }\n')
        for directory, source in (('good', 'good.c'), ('wrong', 'wrong.c')):
            (cls.root / directory).mkdir()
            subprocess.run(['gcc', '-shared', '-fPIC', '-Wl,-soname,libbase.so',
                            f'-Wl,--version-script={cls.root}/version.map', '-o',
                            str(cls.root / directory / 'libbase.so'), str(cls.root / source)],
                           check=True, capture_output=True)
        subprocess.run(['gcc', '-o', str(cls.root / 'consumer'), str(cls.root / 'main.c'),
                        '-L' + str(cls.root / 'good'), '-lbase'], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_real_versioned_symbol_match_and_nonmatch(self):
        consumer = (self.root / 'consumer').read_bytes()
        needed = audit.consumer_references(consumer, {'libbase.so'})
        self.assertEqual(needed['status'], 'read')
        self.assertIn(('libbase.so', 'present', 'ABI_1', 'strong'), needed['references'])
        self.assertFalse(audit.consumer_references(consumer, set())['references'])
        good = audit.provider_exports((self.root / 'good/libbase.so').read_bytes())
        wrong = audit.provider_exports((self.root / 'wrong/libbase.so').read_bytes())
        self.assertIn(('present', 'ABI_1'), good['exports'])
        self.assertNotIn(('present', 'ABI_1'), wrong['exports'])

    def test_collector_reports_observations_not_abi_verdict(self):
        consumer = (self.root / 'consumer').read_bytes()
        provider = (self.root / 'good/libbase.so').read_bytes()
        collector = audit.Collector()
        collector.capture_provider(fake_entry(provider), len(provider), 64, 'libbase.so')
        parsed = {'class': 64, 'architecture': 'AArch64', 'type': 'dynamic',
                  'interpreter': '/system/bin/linker64'}
        collector.capture_consumer(fake_entry(consumer), len(consumer), parsed)
        result = collector.summarize()
        self.assertEqual(result['consumer_executable_stats']['with_selected_versioned_references'], 1)
        rows = [r for r in result['observations'] if r['library'] == 'libbase.so']
        self.assertEqual(rows[0]['observation'], 'same_symbol_and_version_seen_in_named_apex_library')
        self.assertEqual(rows[0]['distinct_symbol_version_pairs'], 1)
        self.assertNotIn('present', str(result))  # no raw symbol names in the report
        self.assertIn('do not establish ABI or boot', result['limitations'][-1])

    def test_provider_absence_is_not_reported_as_a_mismatch(self):
        consumer = (self.root / 'consumer').read_bytes()
        collector = audit.Collector()
        parsed = {'class': 64, 'architecture': 'AArch64', 'type': 'dynamic',
                  'interpreter': '/system/bin/linker64'}
        collector.capture_consumer(fake_entry(consumer), len(consumer), parsed)
        result = collector.summarize()
        self.assertEqual(result['observations'][0]['observation'], 'not_compared_no_readable_version_definitions')

    def test_short_and_oversized_elf_are_rejected(self):
        with self.assertRaises(audit.SymbolProbeError):
            audit.provider_exports(b'\x7fELF')
        with self.assertRaises(audit.SymbolProbeError):
            audit.read_entry(fake_entry(b''), audit.MAX_ELF + 1)
        with self.assertRaises(audit.SymbolProbeError):
            audit.read_entry(fake_entry(b'abc'), 4)


if __name__ == '__main__':
    unittest.main()
