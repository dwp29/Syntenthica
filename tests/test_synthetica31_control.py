import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('control', ROOT/'build-kit/scripts/build_synthetica31_control.py')
m=importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

class ControlTests(unittest.TestCase):
    def setUp(self):
        source=os.environ.get('S31_EXACT_CONFIG')
        if not source: self.skipTest('exact 3.1 config not supplied')
        self.reference=Path(source)
        self.old=self.reference.read_text()
        self.new=self.old.replace('CONFIG_LOCALVERSION="-synthetica-3.1"','CONFIG_LOCALVERSION="-synthetica-3.1-control1"').replace('CONFIG_LRU_GEN_ENABLED=y','# CONFIG_LRU_GEN_ENABLED is not set')
    def test_only_two_changes(self):
        d=m.compare_config(self.reference,self.new)
        self.assertEqual(set(d),{'LOCALVERSION','LRU_GEN_ENABLED'})
        self.assertEqual(d['LRU_GEN_ENABLED'],{'3.1':'y','control1':'n'})
    def test_unrelated_security_change_rejected(self):
        bad=self.new.replace('CONFIG_MODULE_SIG_FORCE=y','# CONFIG_MODULE_SIG_FORCE is not set')
        with self.assertRaises(ValueError): m.compare_config(self.reference,bad)
    def test_default_on_rejected(self):
        with self.assertRaises(ValueError): m.compare_config(self.reference,self.new.replace('# CONFIG_LRU_GEN_ENABLED is not set','CONFIG_LRU_GEN_ENABLED=y'))
    def test_changed_reference_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'ref';p.write_text(self.old+'\n# changed\n')
            with self.assertRaises(ValueError): m.compare_config(p,self.new)
    def test_guard_chain_on_actual_config(self):
        test=os.environ.get('S3RC_TESTED_CONFIG')
        if not test: self.skipTest('pinned tested reference not supplied')
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'config';p.write_text(self.new)
            report=m.check_config(ROOT/'artifacts/generated.config.txt',p,Path(test),'off')
            self.assertEqual(report['changes_from_exact_3_1']['LRU_GEN_ENABLED']['control1'],'n')
            p.write_text(self.new.replace('CONFIG_MODVERSIONS=y','# CONFIG_MODVERSIONS is not set'))
            with self.assertRaises(ValueError): m.check_config(ROOT/'artifacts/generated.config.txt',p,Path(test),'off')

if __name__=='__main__': unittest.main()
