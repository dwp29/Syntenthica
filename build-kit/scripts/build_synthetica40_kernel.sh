#!/usr/bin/env bash
# Linux 6.18 development build ONLY. It never creates a boot image or installer.
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
: "${S40_SOURCE:?Set S40_SOURCE to the prepared disposable kernel tree}"
: "${S40_OUT:?Set S40_OUT to a disposable output directory}"
src=$(realpath "$S40_SOURCE")
out=$(realpath -m "$S40_OUT")
if [[ $out == / || $out == "$root" || $out == "$root/"* || $root == "$out/"* || \
      $out == "$src" || $out == "$src/"* || $src == "$out/"* ]]; then
  echo 'Refusing output in the repository, source tree, or their ancestors.' >&2
  exit 1
fi
mkdir -p "$out"
if [[ ! -f "$src/drivers/kernelsu/Kbuild" || ! -f "$src/fs/nomount/nomount.c" ]]; then
  echo 'Prepared KernelSU/NoMount source is missing.' >&2
  exit 1
fi
export ARCH=arm64 LLVM=1
export KBUILD_BUILD_USER=synthetica KBUILD_BUILD_HOST=experimental
export KBUILD_BUILD_TIMESTAMP='2026-10-26 00:00:00 +0000'
export KBUILD_BUILD_VERSION=1
hostcc=${HOSTCC:-gcc}
make_args=(-C "$src" O="$out" "HOSTCC=$hostcc")
make "${make_args[@]}" defconfig
# Match upstream miatoll/build.sh: turn defconfig modules off and prune other
# SoCs before applying the miatoll, Android and Synthetica fragments.
python3 - "$src" "$out/.config" <<'PY'
from pathlib import Path
import re, subprocess, sys
src, config = map(Path, sys.argv[1:])
lines = config.read_text().splitlines()
config.write_text('\n'.join('# ' + x[:-2] + ' is not set' if x.endswith('=m') else x
                            for x in lines) + '\n')
for name in re.findall(r'^config (ARCH_[A-Z0-9_]+)$',
                       (src/'arch/arm64/Kconfig.platforms').read_text(), re.M):
    if name != 'ARCH_QCOM':
        subprocess.run([str(src/'scripts/config'), '--file', str(config), '--disable', name], check=True)
PY
fragments=(
  "$src/miatoll/configs/sm7125-prune.config"
  "$src/miatoll/configs/miatoll.config"
  "$src/miatoll/configs/lineage1.config"
  "$root/build-kit/ci/synthetica40/experimental.config"
)
"$src/scripts/kconfig/merge_config.sh" -m -O "$out" "$out/.config" "${fragments[@]}"
make "${make_args[@]}" olddefconfig
python3 "$root/build-kit/scripts/build_synthetica40.py" check-config "$out/.config" "${fragments[@]}"
if [[ ${S40_CONFIG_ONLY:-0} == 1 ]]; then
  echo 'Configuration validated; compilation deliberately skipped.'
  exit 0
fi
jobs=${S40_JOBS:-4}
if [[ ! $jobs =~ ^[1-9][0-9]*$ || $jobs -gt 64 ]]; then
  echo 'S40_JOBS must be a positive integer <= 64.' >&2
  exit 1
fi
make "${make_args[@]}" -j"$jobs" Image dtbs modules
# Module signing uses a freshly generated build key. Never export this key or
# assume the target ROM trusts it. Keep installation output in scratch only.
: "${S40_MODULES:?Set S40_MODULES to a disposable modules-install directory}"
modules=$(realpath -m "$S40_MODULES")
if [[ $modules == / || $modules == "$root" || $modules == "$root/"* || $root == "$modules/"* || \
      $modules == "$src" || $modules == "$src/"* || $src == "$modules/"* ]]; then
  echo 'Refusing unsafe modules-install directory.' >&2
  exit 1
fi
mkdir -p "$modules"
make "${make_args[@]}" "INSTALL_MOD_PATH=$modules" modules_install
make -s "${make_args[@]}" kernelrelease
