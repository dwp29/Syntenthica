"""Test the 3.2 evidence wording correction; no firmware/ROM/device access."""
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'build-kit/scripts'))
import correct_synthetica32_evidence as fix


def sha(data):
    return hashlib.sha256(data).hexdigest()


def blob(data):
    return hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()


class CorrectionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.original = self.root/'original.zip'
        self.out = self.root/'corrected.zip'
        self.files = {name: ('synthetic: '+name).encode() for name in fix.audit.MEMBERS}
        self.files[fix.audit.build.IMAGE_NAME] = b'synthetic-not-a-real-kernel'
        self.status = {'status': 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED',
                       'uname_release': fix.audit.build.RELEASE, 'checks_not_proofs': [fix.WRONG, 'other']}
        self.write_original()

    def write_original(self):
        self.files['STATUS.json'] = json.dumps(self.status).encode()
        self.files['SHA256SUMS.txt'] = ''.join(f'{sha(self.files[name])}  {name}\n'
                                               for name in sorted(fix.audit.MEMBERS - {'SHA256SUMS.txt'})).encode()
        mem = io.BytesIO()
        with zipfile.ZipFile(mem, 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for name, data in self.files.items():
                z.writestr(name, data)
        self.original.write_bytes(mem.getvalue())
        self.orig_sha = sha(mem.getvalue())
        self.orig_blob = blob(mem.getvalue())

    def call(self, out=None):
        with mock.patch.object(fix, 'ORIGINAL_SHA256', self.orig_sha), \
             mock.patch.object(fix, 'ORIGINAL_BLOB', self.orig_blob), \
             mock.patch.object(fix, 'IMAGE_SHA256', sha(self.files[fix.audit.build.IMAGE_NAME])):
            return fix.correct(self.original, out or self.out)

    def test_correction_changes_only_status_and_manifest_and_is_deterministic(self):
        info = self.call()
        with zipfile.ZipFile(self.out) as z:
            data = {name: z.read(name) for name in z.namelist()}
        self.assertEqual({n for n in self.files if self.files[n] != data[n]}, {'STATUS.json', 'SHA256SUMS.txt'})
        fix.audit.verify_manifest(data)
        status = json.loads(data['STATUS.json'])
        self.assertIn(fix.CORRECT, status['checks_not_proofs'])
        self.assertNotIn(fix.WRONG, status['checks_not_proofs'])
        self.assertEqual(status['evidence_status_text_correction']['original_ci_transfer_sha256'], self.orig_sha)
        self.assertEqual(info['image_sha256'], sha(data[fix.audit.build.IMAGE_NAME]))
        second = self.root/'second.zip'
        again = self.call(second)
        self.assertEqual(info['sha256'], again['sha256'])
        self.assertEqual(self.out.read_bytes(), second.read_bytes())

    def test_refuses_wrong_hash_status_and_existing_output(self):
        self.original.write_bytes(self.original.read_bytes() + b'changed')
        with self.assertRaisesRegex(ValueError, 'archive hash'):
            self.call()
        self.assertFalse(self.out.exists())
        self.status['checks_not_proofs'] = ['no wrong sentence']
        self.write_original()
        with self.assertRaisesRegex(ValueError, 'unexpected original'):
            self.call()
        self.assertFalse(self.out.exists())
        self.out.write_bytes(b'keep')
        with self.assertRaisesRegex(ValueError, 'overwrite'):
            self.call()
        self.assertEqual(self.out.read_bytes(), b'keep')


@unittest.skipUnless(os.environ.get('S32_ORIGINAL_EVIDENCE') and os.environ.get('S32_EVIDENCE'),
                     'exact original and corrected public CI evidence not provided')
class RealCorrectionTests(unittest.TestCase):
    def test_exact_original_reproduces_published_member_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d)/'corrected.zip'
            fix.correct(Path(os.environ['S32_ORIGINAL_EVIDENCE']), out)
            with zipfile.ZipFile(out) as generated, zipfile.ZipFile(os.environ['S32_EVIDENCE']) as published:
                self.assertEqual(set(generated.namelist()), set(published.namelist()))
                for name in generated.namelist():
                    self.assertEqual(generated.read(name), published.read(name), name)
            # DEFLATE representations may differ between zlib versions even
            # when the corrected member contents are exactly reproducible.


if __name__ == '__main__':
    unittest.main()
