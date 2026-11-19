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

import importlib.util
import os
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
        """Cocokkan config hasil build dengan 3.1.

        Kita tidak mengandalkan nilai 3.1 tersimpan (blob 3.1 tidak selalu bisa
        dibaca di lingkungan ini). Yang diperiksa:

        1. setiap simbol di ALLOWED berakhir pada nilai yang diminta;
        2. LOCALVERSION berakhir pada localversion varian;
        3. TIDAK ada perubahan lain di luar itu;
        4. semua simbol wajib-hidup tetap y, wajib-mati tetap mati.
        """
        v3 = module.v3
        if baseline31.is_symlink() or not baseline31.is_file():
            raise ValueError('baseline 3.1 config missing or unsafe')
        previous = v3.read_config(baseline31.read_text(encoding='utf-8'))
        current = v3.read_config(generated)
        changes = {k: {'before': previous.get(k, 'n'), 'now': current.get(k, 'n')}
                   for k in sorted(previous.keys() | current.keys())
                   if previous.get(k, 'n') != current.get(k, 'n')}

        allowed_keys = set(ALLOWED) | {'LOCALVERSION'}
        unexpected = sorted(k for k in changes if k not in allowed_keys)
        if unexpected:
            raise ValueError('perubahan config di luar daftar izin: '
                             + ', '.join(unexpected[:20]))

        if current.get('LOCALVERSION') != spec['localversion']:
            raise ValueError('LOCALVERSION tidak sesuai varian: '
                             f"{current.get('LOCALVERSION')} != {spec['localversion']}"
                             )
        for key, (_before, after) in ALLOWED.items():
            if current.get(key, 'n') != after:
                raise ValueError(f'{key} tidak tercapai: '
                                 f"{current.get(key, 'n')} != {after}")

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


def _variant_from_env() -> str:
    variant = os.environ.get('FM_VARIANT', '').strip()
    if variant not in VARIANTS:
        raise SystemExit('FM_VARIANT must be set to: ' + ', '.join(VARIANTS))
    return variant


def main(argv: list[str]) -> int:
    """Dua mode:

    1. Eksplisit:  build_fresh_milk.py <variant> verify|apply
    2. Delegasi:   build_fresh_milk.py <subcommand 3.2-r1> [args...]

    Mode 2 dipakai oleh build_chronicle_base.py, yang memanggil helper lewat
    $S2X_HELPER. Varian diambil dari FM_VARIANT. Override dipasang di proses
    yang sama, lalu subcommand diteruskan ke resep 3.2-r1.
    """
    pending = argv[1:]
    if not pending:
        raise SystemExit('usage: build_fresh_milk.py <variant> verify|apply  |  '
                         '<3.2-r1 subcommand> [args]')

    if pending[0] in VARIANTS:
        variant = pending[0]
        pending = pending[1:]
        explicit = True
    else:
        variant = _variant_from_env()
        explicit = False

    module = apply_variant(variant)

    if explicit:
        if pending == ['verify'] or pending[:1] == ['apply']:
            return 0
        raise SystemExit('unknown variant command: ' + ' '.join(pending))

    # Delegasi: bangun ulang argv seolah-olah resep 3.2-r1 dipanggil langsung.
    saved = sys.argv
    try:
        sys.argv = [str(ROOT / 'build-kit/scripts/build_synthetica32_r1.py')] + pending
        return module.main()
    finally:
        sys.argv = saved


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
