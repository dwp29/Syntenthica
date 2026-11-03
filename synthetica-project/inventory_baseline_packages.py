#!/usr/bin/env python3
"""Read-only presence inventory of selected preinstalled package manifests.

Only selected names under allocated app/priv-app paths in the verified system,
system_ext and product images are reported. Presence is not proof of an
installed, licensed, functional or certified app. No images are modified.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
import zipfile

import audit_vintf_candidate as vintf
import preflight_spatialflow as pre
import scan_apk_packages as scan
import verify_preservation as guard

WATCH = {
    'com.android.vending', 'com.google.android.gms', 'com.google.android.gsf',
    'com.google.android.setupwizard', 'com.android.settings', 'com.android.systemui',
    'com.android.phone', 'com.android.dialer', 'com.google.android.dialer',
    'com.android.contacts', 'com.google.android.contacts', 'com.android.mms',
    'com.google.android.apps.messaging', 'com.google.android.inputmethod.latin',
    'com.android.inputmethod.latin', 'com.android.camera', 'com.android.camera2',
    'com.miui.camera', 'com.android.nfc', 'com.miui.securitycenter',
    'com.android.providers.media', 'com.miui.player', 'com.miui.gallery',
    'com.android.axion.sandbox',
}

class InventoryError(RuntimeError):
    pass


def run(work: Path, aapt: str, aapt2: str) -> dict:
    if not work.is_dir() or any(work.iterdir()):
        raise InventoryError('Work directory must be empty')
    lock = json.loads((Path(__file__).parent/'original-baseline.lock.json').read_text())
    source = pre.download_candidate(work)
    extents = pre.extract_extents(source, work, lock)
    for name, item in extents.items():
        if pre.digest_file(item['path']) != (item['window']['bytes'], item['window']['sha256']):
            raise InventoryError('Partition copy failed independent readback: ' + name)
    scratch = work/'package-scan'; scratch.mkdir()
    result = scan.scan({n:x['path'] for n,x in extents.items()}, aapt, scratch, pre.APP_PACKAGE,
                       aapt2=aapt2, watch_packages=WATCH)
    for name, item in extents.items():
        if pre.digest_file(item['path']) != (item['window']['bytes'], item['window']['sha256']):
            raise InventoryError('Partition copy changed during read-only scan: ' + name)
    if pre.digest_file(source) != (pre.SOURCE_SIZE, pre.SOURCE_SHA256):
        raise InventoryError('Source ZIP changed during read-only scan')
    return {'schema':'synthetica-baseline-package-inventory-v1',
            'status':'READ_ONLY_INVENTORY_NOT_A_DEVICE_TEST_HOLD',
            'source_candidate03_sha256':pre.SOURCE_SHA256,
            'all_extracted_input_extents_unchanged':True, 'scan':result,
            'limitations':['APK presence in a scanned root is not proof of installation, function, certification or license.',
                'No matches means only no match in these scanned roots; APEX, symlink targets, ODM/vendor and dynamic apps are excluded.',
                'No source image, release, device, recovery or ROM was modified or published.']}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--work',type=Path,required=True);p.add_argument('--report',type=Path,required=True)
    p.add_argument('--aapt',required=True);p.add_argument('--aapt2',required=True)
    args=p.parse_args()
    try:
        result=run(args.work,args.aapt,args.aapt2);code=0
    except (InventoryError,pre.PreflightError,vintf.VintfAuditError,scan.PackageScanError,
            guard.AuditError,OSError,ValueError,zipfile.BadZipFile) as exc:
        result={'schema':'synthetica-baseline-package-inventory-v1','status':'INVENTORY_FAILED_HOLD',
                'error':str(exc),'device_modified':False};code=1
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,separators=(',',':')),flush=True);return code

if __name__=='__main__': sys.exit(main())
