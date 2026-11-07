"""Optional real-tool integration: ephemeral test key, never the real Manager key.

Exercises refusal of a wrong key and the local-signing mechanics in a PTY. The
happy-path monkeypatch is strictly inside this test process, using only a newly
generated throwaway certificate; production never changes the pinned identity.
"""
from __future__ import annotations

import errno
import importlib.util
import os
from pathlib import Path
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SIGNER_PATH = ROOT / 'build-kit/scripts/sign_manager_31_locally.py'
spec = importlib.util.spec_from_file_location('neon31_signer_integration', SIGNER_PATH)
assert spec and spec.loader
signer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(signer)


@unittest.skipUnless(os.environ.get('NEON31_SIGNING_INTEGRATION') == '1', 'Android signing integration is opt-in')
class InteractiveSigning31Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='neon31-sign-fake-')
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.passphrase = 'synthetica-ephemeral-ci-test'
        cls.passfile = cls.root / 'test-only-password.txt'
        cls.passfile.write_text(cls.passphrase + '\n')
        cls.passfile.chmod(0o600)
        cls.keystore = cls.root / 'throwaway.p12'
        cls.apk = Path(os.environ['NEON31_UNSIGNED_APK']).resolve()
        cls.tools = Path(os.environ['NEON31_ANDROID_BUILD_TOOLS']).resolve()
        cls.keytool = shutil.which('keytool')
        if not cls.keytool:
            raise RuntimeError('keytool is required for the opt-in signing integration')
        subprocess.run([cls.keytool, '-genkeypair', '-keystore', str(cls.keystore), '-alias', 'throwaway',
                        '-storetype', 'PKCS12', '-keyalg', 'RSA', '-keysize', '2048', '-validity', '1',
                        '-dname', 'CN=Ephemeral CI test only,O=Not trusted',
                        '-storepass:file', str(cls.passfile), '-keypass:file', str(cls.passfile), '-noprompt'],
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        listing = subprocess.check_output([cls.keytool, '-J-Duser.language=en', '-J-Duser.country=US',
                                           '-list', '-v', '-keystore', str(cls.keystore), '-alias', 'throwaway',
                                           '-storepass:file', str(cls.passfile)], text=True)
        cls.fake_cert = signer.keytool_certificate(listing)
        if cls.fake_cert == signer.EXPECTED_CERT:
            raise AssertionError('Throwaway test signer must not equal the real pinned identity')
        cls.harness = cls.root / 'pty_harness.py'
        cls.harness.write_text('''import importlib.util,os,sys\np=os.environ["SIGNER_PATH"]\nspec=importlib.util.spec_from_file_location("pty_signer",p)\nm=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)\nif os.environ.get("ALLOW_FAKE_CERT")=="1": m.EXPECTED_CERT=os.environ["FAKE_CERT"]\nsys.argv=[p,*sys.argv[1:]]\ntry: m.main()\nexcept Exception as e:\n print("Signing refused:",e,file=sys.stderr);sys.exit(1)\n''')

    def run_interactive(self, output: Path, allow_fake: bool) -> tuple[int, str]:
        import hashlib
        args = [sys.executable, str(self.harness), '--apk', str(self.apk),
                '--expected-sha256', hashlib.sha256(self.apk.read_bytes()).hexdigest(),
                '--keystore', str(self.keystore), '--alias', 'throwaway',
                '--build-tools', str(self.tools), '--out', str(output)]
        env = os.environ.copy()
        env.update({'SIGNER_PATH': str(SIGNER_PATH), 'FAKE_CERT': self.fake_cert,
                    'ALLOW_FAKE_CERT': '1' if allow_fake else '0'})
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe(args[0], args, env)
        text = b''
        answered = 0
        deadline = time.monotonic() + 90
        status = None
        try:
            while time.monotonic() < deadline:
                ready, _, _ = select.select([fd], [], [], 0.25)
                if ready:
                    try:
                        chunk = os.read(fd, 8192)
                    except OSError as exc:
                        if exc.errno != errno.EIO:
                            raise
                        chunk = b''
                    text += chunk
                    prompts = re.findall(
                        rb'(?i)(?:enter\s+keystore\s+password|keystore\s+password\s+for\s+signer\s*#?\d+|key\s+password\s+for\s+signer\s*#?\d+)\s*:', text)
                    while answered < len(prompts):
                        os.write(fd, (self.passphrase + '\n').encode())
                        answered += 1
                exited, child_status = os.waitpid(pid, os.WNOHANG)
                if exited:
                    status = os.waitstatus_to_exitcode(child_status)
                    break
            if status is None:
                os.kill(pid, 9)
                os.waitpid(pid, 0)
                raise AssertionError('interactive test timed out: ' + text.decode(errors='replace')[-3000:])
        finally:
            os.close(fd)
        return status, text.decode(errors='replace').replace(self.passphrase, '[ephemeral-test-password]')

    def test_rejects_wrong_key_then_signs_with_test_override(self):
        refused = self.root / 'must-not-exist.apk'
        code, output = self.run_interactive(refused, allow_fake=False)
        self.assertNotEqual(code, 0, output)
        self.assertIn('certificate does not match', output.lower())
        self.assertFalse(refused.exists())

        signed = self.root / 'fake-signed-test.apk'
        code, output = self.run_interactive(signed, allow_fake=True)
        self.assertEqual(code, 0, output)
        self.assertTrue(signed.is_file())
        check = subprocess.check_output([str(self.tools / 'apksigner'), 'verify', '--print-certs', str(signed)], text=True)
        self.assertEqual(signer.apksigner_certificate(check), self.fake_cert)


if __name__ == '__main__':
    unittest.main()
