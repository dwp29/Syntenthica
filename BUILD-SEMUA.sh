#!/usr/bin/env bash
# Synthetica 2.0 — build APK dulu, lalu kernel, lalu paket flashable. Satu perintah.
# Semua skrip di build-kit/scripts/ memakai build-kit/ sebagai root (ci/ ada di dalamnya),
# jadi hasil antara selalu berkumpul di build-kit/artifacts/.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KIT="$HERE/build-kit"
JOBS="${1:-4}"
export PATH="/usr/lib/llvm-18/bin:$PATH"

[ -n "${ANDROID_SDK_ROOT:-}" ] || { echo "GAGAL: set ANDROID_SDK_ROOT dulu (lihat BUILD-HOWTO.md)"; exit 1; }
[ -d "$HERE/kernel-tree/arch/arm64" ] || { echo "GAGAL: kernel-tree tidak lengkap"; exit 1; }
[ -d "$HERE/manager-source/manager" ] || { echo "GAGAL: manager-source tidak lengkap"; exit 1; }
[ -f "$HERE/secretkey/synthetica-2.0.p12" ] || { echo "GAGAL: secretkey/synthetica-2.0.p12 hilang"; exit 1; }

mkdir -p "$HERE/out"

echo "=== 1/3 APK Synthetica (glass UI) ==="
# build_manager_source.py mengambil source dari pin yang sama dengan manager-source/
# (KernelSU-Next @ 31946acd) lalu menimpa tema dari build-kit/ci/ksun-overlay/.
( cd "$KIT" && SP_RELEASE_VERSION=2.0 SP_WORK_DIR=/tmp/sp-manager-src-2.0 \
  SP_KEYSTORE="$HERE/secretkey/synthetica-2.0.p12" SP_KEYSTORE_PASS="synthetica-2.0" \
  python3 scripts/build_manager_source.py )
cp -f "$KIT/artifacts/manager/Synthetica-2.0.apk" "$HERE/out/"

echo "=== 2/3 Kernel (basis 1.16, profil synthetica) ==="
( cd "$KIT" && SP_JOBS="$JOBS" SP_RELEASE_VERSION=2.0 SP_PROFILE=synthetica \
  SP_BUILD_NAME=Synthetica SP_BUILD_KVER=2.0 SP_WORK_DIR=/tmp/sp-kernel-2.0 \
  python3 scripts/build_chronicle_base.py )

echo "=== 3/3 Paket flashable ==="
( cd "$KIT" && python3 scripts/package_release.py )
cp -f "$KIT/artifacts/Synthetica-2.0.zip" "$KIT/artifacts/Synthetica-2.0-LOG.zip" "$HERE/out/"

echo
echo "SELESAI -> $HERE/out/"
ls -l "$HERE/out/"
sha256sum "$HERE/out/"*
echo "uname target: 4.14.357-openela-Synthetica-2.0"
echo "Status: COMPILED_ONLY_UNVERIFIED sampai diuji boot di HP."
