#!/usr/bin/env python3
"""Save a statically verified same-build kernel/modules pair; not an installer."""
import argparse
import gzip
import hashlib
import json
import re
from pathlib import Path
import zipfile

import build_synthetica3 as v3
import verify_synthetica3_modules as vm

RELEASE = '4.14.357-openela-synthetica-3.1'


def collect(out: Path, result: Path, destination: Path) -> None:
    if destination.exists() or destination.is_symlink():
        raise ValueError('destination already exists')
    image = (result / 'Image.gz.DO-NOT-FLASH').read_bytes()
    raw = gzip.decompress(image)
    if len(raw) > v3.MAX_RAW_IMAGE:
        raise ValueError('kernel exceeds maximum size')
    if not re.search(rb'Linux version ' + re.escape(RELEASE.encode()) + rb'\s', raw):
        raise ValueError('kernel release mismatch')
    config = (result / 'generated.config.txt').read_bytes()
    v3.verify_embedded_config(raw, config)
    cert = (result / 'module-signing-public-cert.x509').read_bytes()
    symvers_text = (result / 'Module.symvers').read_text()
    stage = out / 'synthetica2-experimental-modules/lib/modules' / RELEASE / 'kernel'
    found = vm.collect(stage, config=v3.read_config(config.decode()), release=RELEASE,
                       certificate_der=cert, raw_kernel=raw, symvers_text=symvers_text)
    status = json.loads((result / 'STATUS.json').read_text())
    for name, (_, checks) in found.items():
        if checks != status['same_build_modules_static_checks'][name]:
            raise ValueError(f'prior build verification differs for {name}')
    files = {'Image.gz.DO-NOT-FLASH': image,
             'generated.config.txt': config,
             'module-signing-public-cert.x509': cert,
             'Module.symvers': symvers_text.encode(),
             'STATUS.json': (result / 'STATUS.json').read_bytes()}
    for name, (content, _) in found.items():
        files['modules.DO-NOT-INSTALL/' + name + '.ko'] = content
    note = ('BUKAN INSTALLER. JANGAN FLASH ATAU PASANG MODUL.\n'
            'Kernel dan keenam modul dibangun bersama dan lolos pemeriksaan statis ABI dan signature.\n'
            'Belum ada prosedur instalasi vendor aman, uji boot, verifikasi AVB, atau uji fungsi.\n'
            'Modul ini bukan milik build 3.1 sebelumnya: jangan campurkan antar build.\n')
    files['BACA-DULU.txt'] = note.encode()
    files['SHA256SUMS.txt'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\n'
                                    for name, data in sorted(files.items())).encode()
    with zipfile.ZipFile(destination, 'x', zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for name, data in sorted(files.items()):
            z.writestr(name, data)
    print('pair_sha256=' + hashlib.sha256(destination.read_bytes()).hexdigest())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', required=True, type=Path)
    p.add_argument('--result', required=True, type=Path)
    p.add_argument('--destination', required=True, type=Path)
    a = p.parse_args()
    collect(a.out, a.result, a.destination)
