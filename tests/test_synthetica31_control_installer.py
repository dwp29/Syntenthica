"""Exercise the recovery writer only with synthetic regular files and fake blockdev."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TEMPLATE=ROOT/'build-kit/ci/s31-control-installer/update-binary'
def sha(b):return hashlib.sha256(b).hexdigest()

@unittest.skipUnless(shutil.which('busybox'), 'host busybox required')
class WriterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        t=Path(self.tmp.name);self.t=t;self.bin=t/'bin';self.bin.mkdir()
        self.block=t/'boot';self.original=b'A'*4096;self.candidate=b'B'*4096
        self.block.write_bytes(self.original)
        (self.bin/'getprop').write_text('''#!/bin/sh
case "$1" in
 ro.product.device) echo "${DEVICE-joyeuse}";;
 ro.boot.slot_suffix) echo "${SLOT-}";;
 ro.build.ab_update) echo "${AB-false}";;
 ro.boot.flash.locked) echo "${LOCKED-0}";;
esac
''');(self.bin/'getprop').chmod(0o755)
        # Test harness wrapper only. Production package contains real ARM BusyBox.
        busy='''#!/bin/sh
case "$1" in
 blockdev) case "$2" in --getsize64) echo "${PARTSIZE-4096}"; exit 0;; --getro) echo "${READONLY-0}"; exit 0;; esac;;
 dd) [ "${MODE-}" = writefail ] && exit 1;;
 cmp) [ "${MODE-}" = readbackfail ] && exit 1;;
esac
exec /usr/bin/busybox "$@"
'''
        self.zip=t/'test.zip'
        with zipfile.ZipFile(self.zip,'w') as z:
            z.writestr('tools/busybox',busy);z.writestr('boot.img',self.candidate)
        script=TEMPLATE.read_text().replace('@REFERENCE@',sha(self.original)).replace('@CANDIDATE@',sha(self.candidate))
        script=script.replace('BLOCK=/dev/block/bootdevice/by-name/boot','BLOCK="'+str(self.block)+'"')
        script=script.replace('[ -b "$BLOCK" ]','[ -f "$BLOCK" ]')
        script=script.replace('[ "$partsize" = 134217728 ]','[ "$partsize" = 4096 ]')
        self.entry=t/'update-binary';self.entry.write_text(script)
        self.env=os.environ|{'PATH':str(self.bin)+':'+os.environ['PATH']}
    def run_installer(self,**env):
        return subprocess.run(['busybox','ash',str(self.entry),'3','1',str(self.zip)],env=self.env|env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=25)
    def test_success_writes_and_verifies(self):
        p=self.run_installer();self.assertEqual(p.returncode,0,p.stdout)
        self.assertEqual(self.block.read_bytes(),self.candidate);self.assertIn('readback selesai',p.stdout)
    def test_mismatched_boot_and_preconditions_refuse_without_writes(self):
        for env in ({'DEVICE':'notjoyeuse'},{'SLOT':'_a'},{'AB':'true'},{'LOCKED':'1'},{'LOCKED':''},{'PARTSIZE':'8192'},{'READONLY':'1'}):
            with self.subTest(env=env):
                self.block.write_bytes(self.original);p=self.run_installer(**env)
                self.assertNotEqual(p.returncode,0,p.stdout);self.assertEqual(self.block.read_bytes(),self.original);self.assertNotIn('Menulis partisi boot',p.stdout)
        self.block.write_bytes(b'C'*4096);p=self.run_installer()
        self.assertNotEqual(p.returncode,0,p.stdout);self.assertIn('Boot tidak identik',p.stdout);self.assertEqual(self.block.read_bytes(),b'C'*4096)
    def test_tampered_candidate_is_not_written(self):
        with zipfile.ZipFile(self.zip) as z: busy=z.read('tools/busybox')
        with zipfile.ZipFile(self.zip,'w') as z: z.writestr('tools/busybox',busy);z.writestr('boot.img',b'C'*4096)
        p=self.run_installer();self.assertNotEqual(p.returncode,0,p.stdout);self.assertIn('Hash kandidat salah',p.stdout);self.assertEqual(self.block.read_bytes(),self.original)
    def test_write_or_readback_failure_warns_not_to_reboot(self):
        for mode in ('writefail','readbackfail'):
            with self.subTest(mode=mode):
                self.block.write_bytes(self.original);p=self.run_installer(MODE=mode)
                self.assertNotEqual(p.returncode,0,p.stdout);self.assertIn('JANGAN REBOOT',p.stdout);self.assertNotIn('readback selesai',p.stdout)
    def test_syntax_and_critical_guards(self):
        subprocess.run(['busybox','ash','-n',str(TEMPLATE)],check=True)
        text=TEMPLATE.read_text()
        for token in ('@REFERENCE@','@CANDIDATE@','conv=fsync','cmp -s -n "$partsize"','getsize64','getro','boot_a','boot_b'):
            self.assertIn(token,text)
        for token in ('/data/adb','mount ','reboot\n','vbmeta.img','dtbo.img'):
            self.assertNotIn(token,text)

if __name__=='__main__':unittest.main()

@unittest.skipUnless(os.environ.get('S31_ARM_BB') and shutil.which('qemu-arm-static'), 'ARM QEMU fixture not configured')
class RealArmBusyBoxTests(WriterTests):
    def setUp(self):
        super().setUp()
        arm=Path(os.environ['S31_ARM_BB']).read_bytes()
        with zipfile.ZipFile(self.zip,'w') as z:
            z.writestr('tools/busybox',arm);z.writestr('boot.img',self.candidate)
        entry=self.entry.read_text()
        marker='BB="$WORK/busybox"'
        wrapper='''cat > "$WORK/arm-wrapper" <<'WRAPPER'
#!/bin/sh
case "$1" in
 blockdev) case "$2" in --getsize64) echo "${PARTSIZE-4096}"; exit 0;; --getro) echo "${READONLY-0}"; exit 0;; esac;;
 dd) [ "${MODE-}" = writefail ] && exit 1;;
 cmp) [ "${MODE-}" = readbackfail ] && exit 1;;
esac
exec qemu-arm-static "$AK_TEST_BB" "$@"
WRAPPER
chmod 700 "$WORK/arm-wrapper"
BB="$WORK/arm-wrapper"
export AK_TEST_BB="$WORK/busybox"'''
        assert entry.count(marker)==1
        self.entry.write_text(entry.replace(marker,wrapper))
    def test_arm_busybox_runs_sha_dd_cmp_and_rejections(self):
        p=self.run_installer();self.assertEqual(p.returncode,0,p.stdout)
        self.assertEqual(self.block.read_bytes(),self.candidate)

@unittest.skipUnless(os.environ.get('S31_PRIVATE_BOOT') and os.environ.get('S31_PRIVATE_PACKAGE') and shutil.which('busybox'), 'private boot/package not provided')
class ActualPrivatePackageTest(unittest.TestCase):
    def test_actual_package_writes_only_scratch_copy_with_host_busybox(self):
        original=Path(os.environ['S31_PRIVATE_BOOT']); archive=Path(os.environ['S31_PRIVATE_PACKAGE'])
        with tempfile.TemporaryDirectory() as tmp:
            t=Path(tmp);bin=t/'bin';bin.mkdir();target=t/'synthetic-boot-file';shutil.copyfile(original,target)
            with zipfile.ZipFile(archive) as z: entry=z.read('META-INF/com/google/android/update-binary').decode()
            expected='BLOCK=/dev/block/bootdevice/by-name/boot'
            self.assertEqual(entry.count(expected),1);entry=entry.replace(expected,'BLOCK="'+str(target)+'"',1)
            self.assertEqual(entry.count('[ -b "$BLOCK" ]'),1);entry=entry.replace('[ -b "$BLOCK" ]','[ -f "$BLOCK" ]',1)
            script=t/'entry';script.write_text(entry)
            (bin/'getprop').write_text('#!/bin/sh\ncase "$1" in ro.product.device) echo joyeuse;; ro.build.ab_update) echo false;; ro.boot.flash.locked) echo 0;; esac\n')
            (bin/'unzip').write_text('#!/bin/sh\nif [ "$3" = tools/busybox ]; then cat "'+str(t/'fakebusy')+'"; else exec /usr/bin/unzip "$@"; fi\n')
            (t/'fakebusy').write_text('''#!/bin/sh
if [ "$1" = blockdev ]; then
  case "$2" in --getsize64) echo 134217728; exit 0;; --getro) echo 0; exit 0;; esac
fi
exec /usr/bin/busybox "$@"
''')
            (bin/'getprop').chmod(0o755);(bin/'unzip').chmod(0o755)
            p=subprocess.run(['busybox','ash',str(script),'3','1',str(archive)],env=os.environ|{'PATH':str(bin)+':'+os.environ['PATH']},text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=120)
            self.assertEqual(p.returncode,0,p.stdout);self.assertIn('readback selesai',p.stdout)
            with target.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
            self.assertEqual(h,'5b772f4a8b8cc24c84ff57d619c63cd0710ff95858687aa4382350339f75564b')
            with original.open('rb') as f: h=hashlib.file_digest(f,'sha256').hexdigest()
            self.assertEqual(h,'d33c01c2fd84faff24c8b80b60ed32df735fc966cff2472b1d30403c3e6fec1f')
