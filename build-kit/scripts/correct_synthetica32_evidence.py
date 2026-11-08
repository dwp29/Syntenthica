#!/usr/bin/env python3
"""Correct one unsupported sentence in the first 3.2 CI evidence archive.

This is a metadata-only correction, not a kernel rebuild. It accepts only the
exact public build-42499760357 transfer, copies all binary payloads unchanged,
changes the inaccurate ROM-signer sentence in STATUS.json, and regenerates
SHA256SUMS. The original CI archive is kept available and is never overwritten.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path
import sys
import zipfile

import audit_synthetica32_rom_modules as audit

ORIGINAL_BLOB = '1c5903d8e306d2339a1af7272c4b715154098a27'
ORIGINAL_SHA256 = '7adfddedb3bacab7304e4b6d8e644451de7730515913e38e3ef54431eeb84895'
IMAGE_SHA256 = 'cb6c953dba1515b710ff0f3d90086afa572903bd702a735aed53af7e31b6e943'
WRONG = 'The kernel release/vermagic changed and the fresh module certificate is not the ROM module signer.'
CORRECT = 'The kernel release/vermagic changed; the fresh module certificate may not match the unknown ROM module signers.'


def correct(original: Path, output: Path) -> dict[str, str]:
    if output.exists() or output.is_symlink():
        raise ValueError('refusing to overwrite an existing output')
    data = audit.read_evidence(original, {'transfer_sha256': ORIGINAL_SHA256, 'transfer_git_blob': ORIGINAL_BLOB})
    audit.verify_manifest(data)
    status = json.loads(data['STATUS.json'])
    limitations = status.get('checks_not_proofs')
    if (status.get('status') != 'SYNTHETICA_3_2_COMPILED_ONLY_NOT_DEVICE_VALIDATED'
            or status.get('uname_release') != audit.build.RELEASE
            or audit.sha(data[audit.build.IMAGE_NAME]) != IMAGE_SHA256
            or not isinstance(limitations, list) or limitations.count(WRONG) != 1):
        raise ValueError('unexpected original 3.2 status or image')
    limitations[limitations.index(WRONG)] = CORRECT
    status['evidence_status_text_correction'] = {
        'scope': 'Metadata wording only; kernel image, modules, config and build provenance are unchanged.',
        'reason': 'The original sentence asserted a ROM signer mismatch without examining ROM signers.',
        'original_ci_transfer_sha256': ORIGINAL_SHA256,
        'original_ci_transfer_git_blob': ORIGINAL_BLOB,
    }
    data['STATUS.json'] = (json.dumps(status, indent=2) + '\n').encode()
    data['SHA256SUMS.txt'] = ''.join(f'{audit.sha(data[name])}  {name}\n'
                                   for name in sorted(audit.MEMBERS - {'SHA256SUMS.txt'})).encode()
    audit.verify_manifest(data)
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            created = True
            for name in sorted(data):
                info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.external_attr = 0o100644 << 16
                archive.writestr(info, data[name], compress_type=zipfile.ZIP_DEFLATED, compresslevel=6)
        raw = output.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        # Re-read the exact bytes created and check that no unmentioned member changed.
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            if set(archive.namelist()) != audit.MEMBERS or archive.testzip():
                raise ValueError('corrected archive failed integrity check')
            if any(archive.read(name) != content for name, content in data.items()):
                raise ValueError('corrected archive does not match the checked members')
        return {'sha256': sha, 'git_blob': blob, 'image_sha256': IMAGE_SHA256}
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(correct(args.original, args.output), indent=2))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, OSError, UnicodeError, KeyError, json.JSONDecodeError, zipfile.BadZipFile) as exc:
        print('Evidence correction refused: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
