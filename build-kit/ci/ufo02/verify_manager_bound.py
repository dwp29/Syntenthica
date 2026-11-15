#!/usr/bin/env python3
"""Buktikan kernel MENERIMA sertifikat sebesar APK kita, bukan menolaknya.

Kenapa ini ada
--------------
drivers/kernelsu/manager/apk_sign.c punya, berurutan:

    #define CERT_MAX_LENGTH 1024
    if (certificate_size != expected_size) return false;
    if (certificate_size > CERT_MAX_LENGTH) { pr_info("cert length overlimit"); return false; }
    char cert[CERT_MAX_LENGTH];

Sertifikat Pure Manager 0.13.7 (dan 0.10.0) berukuran 1373 byte. Karena
EXPECTED_MANAGER_SIZE juga 1373, syarat kedua selalu benar (1373 > 1024), dan
kompiler membuang perbandingannya: alurnya jatuh lurus ke printk "cert length
overlimit" lalu return false. Artinya kernel menolak manager-nya SENDIRI dan
hanya mencetak satu baris di dmesg. Mengganti hash saja tidak pernah cukup.

Cara memeriksanya
-----------------
Disassembly check_block dari image hasil build. Kalau batas atas masih 1024,
tidak ada satu pun perbandingan dengan konstanta di antara 1374..65535. Kalau
batasnya sudah dinaikkan (mis. 4096), konstanta itu muncul sebagai CMP/SUBS.
Ini gagal-bisa-gagal: pada image yang rusak (batas 1024) skrip ini MENOLAK.

usage: verify_manager_bound.py System.map Image[.gz]
"""
import gzip
import pathlib
import struct
import sys

CERT_SIZE = 1373          # ukuran sertifikat v2 APK Pure Manager


def load_image(path):
    data = path.read_bytes()
    if data[:2] == b"\x1f\x8b":
        try:
            return gzip.decompress(data)
        except (EOFError, OSError) as exc:
            raise SystemExit(f"Image tidak bisa dibaca ({exc}); ini BUKAN lulus.")
    return data


def parse_map(path):
    syms = {}
    for line in path.read_text(errors="replace").splitlines():
        p = line.split()
        if len(p) >= 3:
            try:
                syms[p[2]] = int(p[0], 16)
            except ValueError:
                pass
    return syms


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2
    img = load_image(pathlib.Path(argv[1]))
    syms = parse_map(pathlib.Path(argv[2]))
    if "check_block" not in syms or "_stext" not in syms:
        raise SystemExit("check_block tidak ada di System.map; tidak bisa menjawab")

    stext = syms["_stext"]
    start = syms["check_block"]
    after = [v for v in syms.values() if v > start]
    size = min(after) - start
    base = start - stext + 0x800
    if base < 0 or base + size > len(img):
        raise SystemExit("check_block di luar image; tidak bisa menjawab")

    words = struct.unpack_from("<%dI" % (size // 4), img, base)

    saw_exact = False
    bound = None
    for w in words:
        # SUBS/CMP immediate, 32- and 64-bit forms
        if (w & 0xFF800000) in (0x71000000, 0xF1000000):
            imm = (w >> 10) & 0xFFF
            if (w >> 22) & 0x3 == 1:
                imm <<= 12
            if imm == CERT_SIZE:
                saw_exact = True
            elif CERT_SIZE < imm <= 65536:
                bound = imm
        # MOVZ 32/64-bit, useful when the compiler materialises the bound
        elif (w & 0x7F800000) in (0x52800000, 0xD2800000):
            imm = (w >> 5) & 0xFFFF
            if imm == CERT_SIZE:
                saw_exact = True
            elif CERT_SIZE < imm <= 65536:
                bound = imm

    print(f"check_block : {size} byte, {len(words)} instruksi")
    print(f"cocok ukuran: {'ya' if saw_exact else 'tidak'}")
    print(f"batas atas  : {bound if bound else 'TIDAK ADA (masih 1024)'}")
    print()
    if not saw_exact:
        print("TIDAK BISA DIJAWAB: tidak ada perbandingan dengan ukuran sertifikat.")
        return 2
    if bound is None:
        print(f"GAGAL: kernel menolak sertifikat {CERT_SIZE} byte.")
        print("       Tidak ada perbandingan dengan batas di atas 1373, jadi syarat")
        print("       'certificate_size > CERT_MAX_LENGTH' selalu benar.")
        return 1
    print(f"LULUS: batas {bound} > sertifikat {CERT_SIZE}, APK kita bisa diterima.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
