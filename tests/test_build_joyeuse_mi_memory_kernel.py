import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'synthetica-project/build_joyeuse_mi_memory_kernel.py'
spec = importlib.util.spec_from_file_location('mi_memory_kernel', SCRIPT)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class MiMemoryKernelExperimentTest(unittest.TestCase):
    def test_preparation_is_disposable_and_security_gated(self):
        source = ROOT / 'build-kit'
        fragment = source / 'ci/rollercoaster/profiles/joyeuse-builtins-experimental.config'
        before = {name: mod.base.digest(source / name) for name in mod.base.PINNED_INPUTS}
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / 'kit'
            mod.prepare(source, dest, fragment)
            builder = (dest / 'ci/rollercoaster/build-rollercoaster.sh').read_text()
            driver = (dest / 'scripts/build_chronicle_base.py').read_text()
            self.assertIn("grep -qx 'CONFIG_MI_MEMORY_SYSFS=y'", builder)
            self.assertIn("^CONFIG_DEBUG_FS=", builder)
            self.assertIn('"SP_MI_MEMORY_PROBE"', driver)
            self.assertNotIn('# --- kemas AnyKernel3', builder)
            self.assertIn('CONFIG_MI_MEMORY_SYSFS=y', (dest / 'ci/rollercoaster/profiles/synthetica.config').read_text())
        self.assertEqual(before, {name: mod.base.digest(source / name) for name in mod.base.PINNED_INPUTS})

    def test_finish_rejects_missing_driver_or_debugfs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'out'
            out.mkdir()
            for config in ('# CONFIG_MI_MEMORY_SYSFS is not set\n', 'CONFIG_MI_MEMORY_SYSFS=y\nCONFIG_DEBUG_FS=y\n'):
                (out / '.config').write_text(config)
                with self.assertRaisesRegex(ValueError, 'mi_memory'):
                    mod.finish(root / 'kit', out, root / 'baseline', root / 'result')

    def test_finish_records_donor_and_omissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / 'out'
            out.mkdir()
            (out / '.config').write_text('CONFIG_MI_MEMORY_SYSFS=y\n# CONFIG_DEBUG_FS is not set\n')
            def fake_finish(kit, out, baseline, result):
                result.mkdir()
                (result / 'STATUS.json').write_text('{}')
            with patch.object(mod.base, 'finish', fake_finish):
                result = root / 'result'
                mod.finish(root / 'kit', out, root / 'baseline', result)
            report = json.loads((result / 'STATUS.json').read_text())
            self.assertEqual(report['mi_memory_backport']['matches_joyeuse_module'], 'NOT_PROVEN')
            self.assertEqual(report['mi_memory_backport']['unsupported_debug_attributes_omitted'], mod.OMITTED)
            self.assertIn('DO NOT FLASH', (result / 'README-DO-NOT-FLASH.txt').read_text())


if __name__ == '__main__':
    unittest.main()
