#!/usr/bin/env python3
"""Opt-in ARM BusyBox/MagiskBoot tests on synthetic files only, not a device."""
from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
import re
import shlex
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('compat_fixtures_qemu', ROOT / 'tests/test_synthetica3_compat.py')
base = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(base)


@unittest.skipUnless(os.environ.get('S3_COMPAT_QEMU') == '1', 'ARM/QEMU integration is opt-in')
class ArmAuditTests(base.AuditScriptTests):
    def setUp(self):
        super().setUp()
        arm_bb = Path(os.environ['S3_ARM_BB']).resolve()
        self.magiskboot = Path(os.environ['S3_ARM_MAGISKBOOT']).resolve()
        self.assertTrue(arm_bb.is_file())
        self.assertTrue(self.magiskboot.is_file())
        self.wrapper_bb('qemu-arm-static ' + shlex.quote(str(arm_bb)))
        self.shell = ['qemu-arm-static', str(arm_bb), 'ash']

    def test_hash_matches_real_magiskboot_unpack_for_single_and_multi_dtb(self):
        for tree in (base.fixture.fdt(), base.fixture.fdt() + base.fixture.fdt(b'second\0') + b'padding'):
            with self.subTest(size=len(tree)):
                self.make_boot(tree=tree, second=b'', recovery=b'')
                before = base.sha(self.boot)
                p = self.audit()
                self.assertEqual(p.returncode, 0, p.stdout)
                parts = re.findall(r'DTB SHA256 [12]/2: ([0-9a-f]{32})', p.stdout)
                out = self.t / ('magisk-unpack-' + str(len(tree)))
                out.mkdir()
                extract = subprocess.run(['qemu-arm-static', str(self.magiskboot), 'unpack', '-n', str(self.boot)],
                                         cwd=out, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True, timeout=45)
                self.assertEqual(extract.returncode, 0, extract.stdout)
                dtb = (out / 'dtb').read_bytes()
                self.assertEqual(''.join(parts), hashlib.sha256(dtb).hexdigest(),
                                 'diagnostic hash must match the installer DTB guard')
                self.assert_read_only(before)


if __name__ == '__main__':
    unittest.main()
