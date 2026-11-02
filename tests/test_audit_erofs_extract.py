import hashlib
import shutil
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'synthetica-project'))
import audit_erofs_extract as audit
import audit_checkvintf_snapshot as check


class ErofsExtractTests(unittest.TestCase):
    def test_tools_are_pinned_and_untrusted_archives_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sandbox = root / 'sandbox'
            (sandbox / 'tool').mkdir(parents=True)
            archive = root / 'fake.zip'
            with zipfile.ZipFile(archive, 'w') as z:
                z.writestr('bin/fsck.erofs', b'fake fsck')
                z.writestr('bin/mkfs.erofs', b'fake mkfs')
            proc = subprocess.CompletedProcess([], 0, stdout='\n'.join(
                f'0x1 (NEEDED) Shared library: [{x}]' for x in check.HOST_LIBS), stderr='')
            with mock.patch.object(audit, 'FSCK_SHA256', hashlib.sha256(b'fake fsck').hexdigest()), \
                 mock.patch.object(audit, 'MKFS_SHA256', hashlib.sha256(b'fake mkfs').hexdigest()), \
                 mock.patch.object(audit.subprocess, 'run', return_value=proc):
                result = audit.prepare_tools(archive, sandbox, check.HOST_LIBS)
            self.assertEqual(result['fsck_erofs_sha256'], hashlib.sha256(b'fake fsck').hexdigest())
            self.assertEqual((sandbox / 'tool/fsck.erofs').stat().st_mode & 0o777, 0o555)
            bad_root = root / 'bad'
            (bad_root / 'tool').mkdir(parents=True)
            with self.assertRaises(audit.ErofsAuditError):
                audit.prepare_tools(archive, bad_root, check.HOST_LIBS)

    def test_failing_synthetic_control_stops_processing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'sandbox/tool').mkdir(parents=True)
            proc = subprocess.CompletedProcess([], 0, stdout=b'', stderr=b'')
            failure = {'tool_exit_code': 1, 'files': [], 'synthetic_log': 'synthetic only'}
            with mock.patch.object(audit.shutil, 'which', return_value='/usr/bin/unshare'), \
                 mock.patch.object(audit.subprocess, 'run', return_value=proc), \
                 mock.patch.object(audit, 'isolated_extract', return_value=failure):
                with self.assertRaisesRegex(audit.ErofsAuditError, 'positive control failed'):
                    audit.run_controls(root / 'sandbox', root)

    @unittest.skipUnless(shutil.which('unshare') and shutil.which('gcc'), 'User namespaces and gcc are required')
    def test_isolated_reader_does_not_follow_linker_symlink(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sandbox = root / 'sandbox'
            for path in ('tool', 'input', 'out'):
                (sandbox / path).mkdir(parents=True)
            source = root / 'synthetic.c'
            source.write_text(r'''#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
int main(void) {
  mkdir("/out/extracted/bin", 0700);
  symlink("/input/payload.erofs", "/out/extracted/bin/linker");
  int fd = open("/out/extracted/bin/linker64", O_WRONLY|O_CREAT|O_TRUNC, 0600);
  if (fd < 0) return 3;
  write(fd, "safe synthetic data", 19);
  close(fd);
  return 0;
}''')
            built = subprocess.run(['gcc', '-static', '-O2', str(source), '-o', str(sandbox / 'tool/fsck.erofs')],
                                   capture_output=True)
            if built.returncode:
                self.skipTest('Static host compiler unavailable')
            (sandbox / 'readonly-marker').write_text('synthetic')
            fixture = root / 'fixture.erofs'
            fixture.write_bytes(b'secret fixture never followed')
            try:
                result = audit.isolated_extract(sandbox, fixture, control=True)
            except audit.ErofsAuditError as exc:
                if 'Operation not permitted' in str(exc):
                    self.skipTest('User/mount namespaces are disabled')
                raise
            self.assertEqual(result['files'][0]['status'], 'missing_unreadable_or_symlink')
            self.assertEqual(result['files'][1]['status'], 'read')
            self.assertEqual(result['files'][1]['sha256'], hashlib.sha256(b'safe synthetic data').hexdigest())
            self.assertNotIn('secret fixture', str(result))

    @unittest.skipUnless(shutil.which('unshare') and Path('/usr/bin/true').is_file() and
                         Path('/lib/x86_64-linux-gnu/libc.so.6').is_file(),
                         'User namespaces and host ELF libraries are required')
    def test_tmpfs_chroot_runs_synthetic_host_tool_without_candidate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sandbox = root / 'sandbox'
            for path in ('tool', 'input', 'out', 'lib/x86_64-linux-gnu', 'lib64'):
                (sandbox / path).mkdir(parents=True)
            shutil.copy2('/usr/bin/true', sandbox / 'tool/fsck.erofs')
            shutil.copyfile('/lib/x86_64-linux-gnu/libc.so.6', sandbox / 'lib/x86_64-linux-gnu/libc.so.6')
            shutil.copyfile('/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2', sandbox / 'lib64/ld-linux-x86-64.so.2')
            (sandbox / 'lib64/ld-linux-x86-64.so.2').chmod(0o555)
            (sandbox / 'readonly-marker').write_text('synthetic')
            fixture = root / 'fixture.erofs'
            fixture.write_bytes(b'not a real filesystem; tool is /usr/bin/true')
            try:
                result = audit.isolated_extract(sandbox, fixture, control=True)
            except audit.ErofsAuditError as exc:
                if 'Operation not permitted' in str(exc):
                    self.skipTest('User/mount namespaces are disabled')
                raise
            self.assertEqual(result['tool_exit_code'], 0)
            self.assertTrue(result['root_read_only'])
            self.assertEqual(result['tmpfs_inode_limit'], 4096)
            self.assertEqual(result['files'][0]['status'], 'missing_unreadable_or_symlink_parent')
            self.assertFalse((sandbox / 'input/payload.erofs').exists())


if __name__ == '__main__':
    unittest.main()
