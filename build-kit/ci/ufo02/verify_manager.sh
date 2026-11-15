#!/bin/bash
# Buktikan kernel ini mengenali APK Pure Manager sebagai manager.
#
# Kenapa perlu: is_manager_apk() di KernelSU-Next tidak mencocokkan nama paket
# (kecuali KSU_MANAGER_PACKAGE di-set saat build). Ia membandingkan panjang
# sertifikat v2 dan sha256-nya dengan yang di-embed saat build. Salah satu angka
# meleset = APK tidak dikenali = semua supercall ditolak, tanpa pesan yang jelas.
#
# Skrip ini membaca dua sisi dan membandingkannya:
#   sisi kernel : -DEXPECTED_MANAGER_SIZE / -DEXPECTED_MANAGER_HASH yang dipakai
#                 build, dikutip balik dari image lewat System.map tidak mungkin --
#                 nilainya konstanta compile-time, jadi yang diperiksa adalah
#                 variabel yang kita berikan, lalu dibuktikan ulang dari APK.
#   sisi APK    : sertifikat v2 diekstrak dari file .apk itu sendiri.
#
# Usage: verify_manager.sh <apk> [size] [hash]
set -euo pipefail

APK="${1:?usage: verify_manager.sh <apk> [expected-size] [expected-hash]}"
WANT_SIZE="${2:-0x55d}"
WANT_HASH="${3:-a2f942452eec1cd8763e6cf33b9937c1a99b3849c62773a73bf444776743f2d8}"

[ -f "$APK" ] || { echo "GAGAL: $APK tidak ada"; exit 1; }

python3 - "$APK" "$WANT_SIZE" "$WANT_HASH" <<'PY'
import hashlib
import struct
import sys

apk, want_size, want_hash = sys.argv[1], sys.argv[2], sys.argv[3].lower()
want_size_i = int(want_size, 0)


def find_der(buf):
    i = 0
    while i < len(buf) - 4:
        if buf[i] == 0x30 and buf[i + 1] == 0x82:
            ln = struct.unpack(">H", buf[i + 2:i + 4])[0]
            if 0x100 < ln < 0x1000 and i + 4 + ln <= len(buf):
                return buf[i:i + 4 + ln]
        i += 1
    return None


data = open(apk, "rb").read()
eocd = data.rfind(b"PK\x05\x06")
if eocd < 0:
    sys.exit("GAGAL: bukan zip/APK")
cd_off = struct.unpack("<I", data[eocd + 16:eocd + 20])[0]
if data[cd_off - 16:cd_off] != b"APK Sig Block 42":
    sys.exit("GAGAL: tidak ada APK Signing Block (APK tidak di-sign v2+)")

size1 = struct.unpack("<Q", data[cd_off - 24:cd_off - 16])[0]
start = cd_off - size1 - 8
pos = start + 8
cert = None
while pos < cd_off - 24:
    pair_len = struct.unpack("<Q", data[pos:pos + 8])[0]
    pair_id = struct.unpack("<I", data[pos + 8:pos + 12])[0]
    body = data[pos + 12:pos + 8 + pair_len]
    if pair_id == 0x7109871A:          # v2
        cert = find_der(body)
        if cert:
            break
    pos += 8 + pair_len

if not cert:
    sys.exit("GAGAL: sertifikat v2 tidak ditemukan")

got_size = len(cert)
got_hash = hashlib.sha256(cert).hexdigest()

ok_size = got_size == want_size_i
ok_hash = got_hash == want_hash

print(f"APK          : {apk}")
print(f"sertifikat   : {got_size} byte (0x{got_size:x})")
print(f"sha256       : {got_hash}")
print(f"kernel butuh : {want_size_i} byte (0x{want_size_i:x})")
print(f"kernel butuh : {want_hash}")
print()
if ok_size and ok_hash:
    print("COCOK: kernel akan mengenali APK ini sebagai manager.")
    sys.exit(0)
print("TIDAK COCOK: kernel akan menolak APK ini sebagai manager.")
if not ok_size:
    print(f"  panjang beda: APK {got_size} vs kernel {want_size_i}")
if not ok_hash:
    print("  hash beda: build memakai sertifikat lain")
sys.exit(1)
PY
