#!/usr/bin/env python3
"""Fresh-Milk-14.03 / CHEESE-BURGER-11.08 — dua varian dari satu tree.

Dibangun di atas resep 3.2-r1 yang sudah lulus 359 tes. Resep lama mengunci
perubahan config hanya ke LOCALVERSION; modul ini melebarkan kunci itu ke
daftar yang **eksplisit dan tertutup**, lalu menambahkan pemeriksaan sendiri
supaya config yang tidak diminta tetap ditolak.

Pemakaian:
    build_fresh_milk.py <variant> apply --patch-only
    build_fresh_milk.py <variant> verify

`apply --patch-only` menimpa kunci config lalu keluar. Pekerjaan build tetap
dilakukan resep 3.2-r1 supaya seluruh penjagaannya tidak terduplikasi.

Yang TIDAK diubah di sini:
- toolchain (Neutron 24, dipin oleh resep lama)
- SuSFS (tetap v2.3.0 sampai ABI v2.4.0 diverifikasi)
- root (tetap KernelSU-Next sampai tahap 2)
- patch (3.2-r1 + guard MGLRU, tidak ditambah)

Dua varian berbagi source dan patch yang sama. Perbedaan hanya fragment config.
"""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
ASSETS = ROOT / 'build-kit/ci/fresh-milk'
COMMON = ASSETS / 'common.config'

VARIANTS = {
    'fresh-milk': {
        'localversion': '"-Fresh-Milk-14.03"',
        'release': '4.14.357-openela-Fresh-Milk-14.03',
        'fragment': ASSETS / 'fresh-milk.config',
        'focus': 'stability',
    },
    'cheese-burger': {
        'localversion': '"-CHEESE-BURGER-11.08"',
        'release': '4.14.357-openela-CHEESE-BURGER-11.08',
        'fragment': ASSETS / 'cheese-burger.config',
        'focus': 'gaming-performance',
    },
}

# Perubahan config yang diizinkan, relatif terhadap 3.1.
# Ditulis sebagai (nilai_3_1, nilai_baru). Harus sama dengan isi fragment.
ALLOWED = {
    'CRYPTO_ZSTD': ('n', 'y'),
    'CRYPTO_LZ4HC': ('n', 'y'),
    'TMPFS_XATTR': ('n', 'y'),
}

# Fitur yang WAJIB tetap hidup. Kalau salah satu hilang, build dibatalkan.
MUST_STAY_ON = (
    'LRU_GEN', 'LRU_GEN_ENABLED', 'UCLAMP_TASK', 'UCLAMP_TASK_GROUP',
    'SCHED_WALT', 'SCHED_TUNE', 'KSU', 'KSU_MANUAL_HOOK', 'KSU_SUSFS',
    'NOMOUNT', 'SECCOMP', 'SECCOMP_FILTER', 'MODULE_SIG_FORCE', 'MODVERSIONS',
    'SECURITY_SELINUX', 'DM_VERITY', 'F2FS_FS', 'EROFS_FS',
    'BPF_SYSCALL', 'BPF_JIT_ALWAYS_ON',
)

# Config yang harus tetap mati, beserta alasannya.
MUST_STAY_OFF = {
    'MODULE_FORCE_LOAD': 'memungkinkan pemuatan modul tanpa tanda tangan',
    'KSU_SUSFS_TRY_UMOUNT':
        'port SuSFS 4.14 tidak membawa susfs_try_umount(); sudah diverifikasi '
        'tidak ada di v2.3.0 maupun v2.4.0',
    'KSU_SUSFS_SUS_MEMFD': 'dimatikan di base 3.2, tidak diubah tanpa alasan',
}

RELEASE_SAFE = ('FRESH-MILK', 'CHEESE-BURGER')


def load(relative: str, name: str):
    path = ROOT / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f'cannot load {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def apply_variant(variant: str) -> None:
    """Titik masuk: timpa kunci config resep 3.2-r1 untuk satu varian."""
    if variant not in VARIANTS:
        raise SystemExit('variant must be one of: ' + ', '.join(VARIANTS))
    spec = VARIANTS[variant]

    module = load('build-kit/scripts/build_synthetica32_r1.py',
                  f'synthetica32_r1_for_{variant.replace("-", "_")}')

    # Resep 3.2-r1 mengunci LOCALVERSION di level modulnya sendiri.
    module.RELEASE = spec['release']
    module.LOCALVERSION = spec['localversion']

    # Turunkan kunci ke rantai yang di-import-nya. Resep 3.2-r1 menyimpan
    # referensi ke base/rc/s2x sebagai variabel modul; kita ubah isinya,
    # bukan membuat salinan baru, supaya pemeriksaannya tetap berjalan.
    allowed = dict(module.old.base.rc.s2x.ALLOWED_CHANGES)
    allowed['LOCALVERSION'] = ('"-Synthetica-2.0"', spec['localversion'])
    for key, (before, after) in ALLOWED.items():
        allowed[key] = (before, after)
    module.old.base.rc.s2x.ALLOWED_CHANGES = allowed

    module.old.base.EXPECTED_RELEASE = spec['release']
    module.old.base.EXPECTED_LOCALVERSION = spec['localversion']
    module.old.base.rc.EXPECTED_RELEASE = spec['release']
    module.old.base.rc.EXPECTED_LOCALVERSION = spec['localversion']
    module.old.base.rc.s2x.EXPECTED_RELEASE = spec['release']

    # compare_31_config pada 3.2-r1 membangun ulang `expected` dari konstanta
    # lokalnya sendiri. Ganti dengan versi yang membaca ALLOWED terbaru.
    original = module.compare_31_config

    def compare_31_config(baseline31: Path, generated: str):
        v3 = module.v3
        if baseline31.is_symlink() or not baseline31.is_file():
            raise ValueError('baseline 3.1 config missing or unsafe')
        previous = v3.read_config(baseline31.read_text(encoding='utf-8'))
        current = v3.read_config(generated)
        changes = {k: {'3.1': previous.get(k, 'n'), 'now': current.get(k, 'n')}
                   for k in sorted(previous.keys() | current.keys())
                   if previous.get(k, 'n') != current.get(k, 'n')}

        expected = {'LOCALVERSION': {'3.1': module.BASE31_LOCALVERSION,
                                     'now': spec['localversion']}}
        for key, (before, after) in ALLOWED.items():
            expected[key] = {'3.1': before, 'now': after}

        if changes != expected:
            unexpected = sorted(k for k in changes.keys() | expected.keys()
                                if changes.get(k) != expected.get(k))
            raise ValueError('perubahan config di luar daftar izin: '
                             + ', '.join(unexpected[:20]))

        for feature in MUST_STAY_ON:
            if current.get(feature) != 'y':
                raise ValueError(f'fitur wajib hilang: {feature}')
        for key, reason in MUST_STAY_OFF.items():
            if current.get(key) == 'y':
                raise ValueError(f'{key} harus tetap mati: {reason}')

        return changes

    module.compare_31_config = compare_31_config
    print(f'variant      : {variant} ({spec["focus"]})')
    print(f'release      : {spec["release"]}')
    print(f'localversion : {spec["localversion"]}')
    print(f'allowed extra: {", ".join(sorted(ALLOWED))}')
    print(f'must stay on : {len(MUST_STAY_ON)} symbols')
    print(f'must stay off: {", ".join(sorted(MUST_STAY_OFF))}')
    print('catatan      : toolchain, SuSFS, root dan patch TIDAK diubah')
    return module


def main(argv: list[str]) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('variant', choices=sorted(VARIANTS))
    sub = p.add_subparsers(dest='command', required=True)
    apply_cmd = sub.add_parser('apply', help='apply variant overrides in-process')
    apply_cmd.add_argument('--patch-only', action='store_true', required=True,
                           help='leave without building')
    sub.add_parser('verify', help='print the resolved variant settings')
    args = p.parse_args(argv[1:])

    apply_variant(args.variant)
    if args.command == 'verify':
        return 0
    if args.command == 'apply':
        print('override terpasang; proyek memanggil resep 3.2-r1 untuk build')
        return 0
    return 2


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
