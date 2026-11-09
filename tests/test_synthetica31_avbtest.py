"""Safety tests; optional actual package is exercised on a temporary file only."""
import hashlib
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('control_fixture', ROOT / 'tests/test_synthetica31_control_installer.py')
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)
control.TEMPLATE = ROOT / 'build-kit/ci/s31-avbtest-installer/update-binary'

@unittest.skipUnless(shutil.which('busybox'), 'host busybox required')
class AVBTestWriter(control.WriterTests):
    pass

@unittest.skipUnless(os.environ.get('S31_ARM_BB') and shutil.which('qemu-arm-static'), 'ARM QEMU fixture not configured')
class AVBTestARM(control.RealArmBusyBoxTests):
    pass

@unittest.skipUnless(os.environ.get('S31_PRIVATE_BOOT') and os.environ.get('S31_AVBTEST_ZIP') and shutil.which('busybox'), 'private inputs not supplied')
class ActualPackageFixture(unittest.TestCase):
    def test_package_writes_only_temp_copy(self):
        original = Path(os.environ['S31_PRIVATE_BOOT'])
        archive = Path(os.environ['S31_AVBTEST_ZIP'])
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp); bin = t / 'bin'; bin.mkdir(); target = t / 'boot-file'; shutil.copyfile(original, target)
            with zipfile.ZipFile(archive) as z:
                self.assertIsNone(z.testzip())
                entry = z.read('META-INF/com/google/android/update-binary').decode()
                candidate = hashlib.sha256(z.read('boot.img')).hexdigest()
            old = 'BLOCK=/dev/block/bootdevice/by-name/boot'
            self.assertEqual(entry.count(old), 1)
            entry = entry.replace(old, 'BLOCK="' + str(target) + '"', 1)
            self.assertEqual(entry.count('[ -b "$BLOCK" ]'), 1)
            entry = entry.replace('[ -b "$BLOCK" ]', '[ -f "$BLOCK" ]', 1)
            script = t/'entry'; script.write_text(entry)
            (bin/'getprop').write_text('#!/bin/sh\ncase "$1" in ro.product.device) echo joyeuse;; ro.build.ab_update) echo false;; ro.boot.flash.locked) echo 0;; esac\n')
            (bin/'unzip').write_text('#!/bin/sh\nif [ "$3" = tools/busybox ]; then cat "'+str(t/'fakebusy')+'"; else exec /usr/bin/unzip "$@"; fi\n')
            (t/'fakebusy').write_text('''#!/bin/sh
if [ "$1" = blockdev ]; then
 case "$2" in --getsize64) echo 134217728; exit 0;; --getro) echo 0; exit 0;; esac
fi
exec /usr/bin/busybox "$@"
''')
            (bin/'getprop').chmod(0o755); (bin/'unzip').chmod(0o755)
            p = subprocess.run(['busybox','ash',str(script),'3','1',str(archive)],
                env=os.environ | {'PATH':str(bin)+':'+os.environ['PATH']},
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
            self.assertEqual(p.returncode, 0, p.stdout)
            self.assertIn('readback selesai', p.stdout)
            with target.open('rb') as f: self.assertEqual(hashlib.file_digest(f, 'sha256').hexdigest(), candidate)
            with original.open('rb') as f: self.assertEqual(hashlib.file_digest(f, 'sha256').hexdigest(),
                'd33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f')

if __name__ == '__main__': unittest.main()
