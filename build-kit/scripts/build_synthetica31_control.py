#!/usr/bin/env python3
"""3.1-based MGLRU-default-off control; compile evidence, not a boot fix."""
from __future__ import annotations
import argparse
import importlib.util
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
RELEASE = '4.14.357-openela-synthetica-3.1-control1'
LOCALVERSION = '"-synthetica-3.1-control1"'
BASE31_CONFIG_SHA = '4b53a2cb030e9aa55ff798a3ee5c773c0eb50e56cd36430d2874adcb56fa236d'

def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError('could not load build guards')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

old = load(ROOT / 'build-kit/scripts/build_synthetica31.py', 's31_for_control')
base = old.base
rc = base.rc
s2x = rc.s2x
v3 = s2x.v3
abi = load(ROOT / 'build-kit/scripts/build_synthetica32_r1.py', 's31_control_abi')
base.EXPECTED_RELEASE = rc.EXPECTED_RELEASE = s2x.EXPECTED_RELEASE = RELEASE
base.EXPECTED_LOCALVERSION = rc.EXPECTED_LOCALVERSION = LOCALVERSION
base.STATUS_KIND = 'SYNTHETICA_3_1_CONTROL1_COMPILE_ONLY'
s2x.ALLOWED_CHANGES = dict(s2x.ALLOWED_CHANGES)
s2x.ALLOWED_CHANGES['LOCALVERSION'] = ('"-Synthetica-2.0"', LOCALVERSION)


def compare_config(reference: Path, text: str) -> dict:
    if reference.is_symlink() or not reference.is_file() or v3.digest(reference) != BASE31_CONFIG_SHA:
        raise ValueError('3.1 config reference missing or hash mismatch')
    previous = v3.read_config(reference.read_text(encoding='utf-8'))
    current = v3.read_config(text)
    delta = {k: (previous.get(k, 'n'), current.get(k, 'n')) for k in previous.keys() | current.keys()
             if previous.get(k, 'n') != current.get(k, 'n')}
    expected = {'LOCALVERSION': ('"-synthetica-3.1"', LOCALVERSION), 'LRU_GEN_ENABLED': ('y', 'n')}
    if delta != expected:
        raise ValueError('unexpected config differences from 3.1: ' + ', '.join(sorted(k for k in delta.keys() | expected.keys() if delta.get(k) != expected.get(k))))
    for k in ('LRU_GEN', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP', 'KSU', 'KSU_SUSFS', 'NOMOUNT', 'MODVERSIONS', 'MODULE_SIG_FORCE', 'SECURITY_SELINUX', 'DM_VERITY'):
        if current.get(k) != 'y':
            raise ValueError('required feature/security config missing: ' + k)
    if current.get('MODULE_FORCE_LOAD', 'n') != 'n':
        raise ValueError('module force-load must remain disabled')
    return {k: {'3.1': a, 'control1': b} for k, (a,b) in sorted(delta.items())}


def check_config(baseline: Path, generated: Path, tested: Path, mglru: str) -> dict:
    if mglru not in ('on', 'off'):
        raise ValueError('invalid mglru mode')
    ref = Path(os.environ['S31_EXACT_CONFIG'])
    text = generated.read_text(encoding='utf-8')
    delta = compare_config(ref, text)
    original = s2x.check_config(v3.verified_baseline(baseline), text, 'off')
    if tested.is_symlink() or not tested.is_file() or v3.digest(tested) != rc.TESTED_CONFIG_SHA256:
        raise ValueError('tested reference config hash mismatch')
    return {'changes_from_saved_2_0': original, 'changes_from_exact_3_1': delta}

# Adapt the private guard chain only: the underlying verifier examines the real
# config and embedded image, using its existing off-mode checks, not a rewritten config.
rc.check_config = check_config
_original_finish = s2x.finish
def finish_off(kit, out, baseline, result, kind, toolchain_bin, neutron_archive, mglru='on'):
    return _original_finish(kit, out, baseline, result, kind, toolchain_bin, neutron_archive, 'off')
s2x.finish = finish_off


def prepare(source: Path, destination: Path, baseline: Path) -> None:
    base.prepare(source, destination, baseline)
    profile = destination / 'ci/rollercoaster/profiles/synthetica.config'
    t = profile.read_text(encoding='utf-8')
    t = s2x.replace_once(t, 'CONFIG_LRU_GEN_ENABLED=y', '# CONFIG_LRU_GEN_ENABLED is not set')
    profile.write_text(t, encoding='utf-8')
    builder = destination / 'ci/rollercoaster/build-rollercoaster.sh'
    t = builder.read_text(encoding='utf-8')
    t = s2x.replace_once(t, '--mglru on', '--mglru off')
    builder.write_text(t, encoding='utf-8')


def finish(kit, out, baseline, tested, baseline31, symvers31, result, toolchain, neutron):
    if result.exists() or result.is_symlink():
        raise ValueError('refusing to overwrite result')
    if Path(os.environ['S31_EXACT_CONFIG']).resolve() != baseline31.resolve():
        raise ValueError('reference paths differ')
    changes = compare_config(baseline31, (out / '.config').read_text(encoding='utf-8'))
    exports = abi.compare_31_exports(symvers31, out / 'Module.symvers')
    base.finish(kit, out, baseline, tested, result, toolchain, neutron)
    status_path = result / 'STATUS.json'
    status = json.loads(status_path.read_text())
    status.update({'kind': 'SYNTHETICA_3_1_CONTROL1_COMPILE_ONLY',
                   'candidate': '3.1 source and patches, MGLRU compiled but default disabled; NOT a proven boot fix',
                   'config_changes_from_3_1': changes, 'exports_vs_3_1': exports,
                   'rom_modules_and_keyring': 'NOT VERIFIED', 'physical_boot': 'NOT TESTED',
                   'avb_ramdisk_dtb_dtbo_and_root': 'NOT VERIFIED'})
    status_path.write_text(json.dumps(status, indent=2)+'\n')
    (result / 'README-DO-NOT-FLASH.txt').write_text('Compile evidence only; NOT a boot image or flashable ZIP.\n3.1 based control: MGLRU is compiled but disabled by default. Cause of boot failure unknown.\nROM modules, signature trust, AVB and physical boot NOT verified.\n')


def main():
    p = argparse.ArgumentParser(); sub = p.add_subparsers(dest='command', required=True)
    prep = sub.add_parser('prepare')
    for n in ('source','destination','baseline'): prep.add_argument('--'+n, type=Path, required=True)
    tree = sub.add_parser('prepare-tree'); tree.add_argument('--tree', type=Path, required=True)
    cfg = sub.add_parser('check-config')
    for n in ('baseline','generated'): cfg.add_argument('--'+n, type=Path, required=True)
    cfg.add_argument('--mglru', default='off'); cfg.add_argument('--tested-config', type=Path, default=Path(os.environ.get('S3RC_TESTED_CONFIG','/nonexistent')))
    done = sub.add_parser('finish')
    for n in ('kit','out','baseline','tested-config','baseline31','symvers31','result','toolchain-bin','neutron-archive'): done.add_argument('--'+n, type=Path, required=True)
    a=p.parse_args()
    if a.command=='prepare': prepare(a.source,a.destination,a.baseline)
    elif a.command=='prepare-tree': base.prepare_tree(a.tree)
    elif a.command=='check-config': print(json.dumps(check_config(a.baseline,a.generated,a.tested_config,a.mglru),indent=2))
    else: finish(a.kit,a.out,a.baseline,a.tested_config,a.baseline31,a.symvers31,a.result,a.toolchain_bin,a.neutron_archive)

if __name__ == '__main__':
    try: main()
    except (ValueError, OSError, KeyError) as exc:
        print('3.1 control build refused:', exc, file=sys.stderr); sys.exit(1)
