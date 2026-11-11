#!/usr/bin/env bash
# Restore everything this session produced into a fresh checkout.
#
# Written after the workspace was reset twice mid-session: files that only lived
# in /home/user (the signing key, the unsigned APK, the built archive) vanished,
# and only what had been pushed to git or uploaded to Drive survived. This script
# makes that recovery one command instead of a re-derivation.
#
# It is safe to re-run: every step is idempotent and verifies what it restores.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

STAGE="${1:-.restore}"
BRANCH="arena/96cbd65a-synthentica"
UNSIGNED_SHA="ca65a9af30348965b35c314d190970638351ca8c16dfaefb49ec299ace781502"
UNSIGNED_BLOB="a497d49c36674a7148ff2123f7b58b4fd926445b"

say() { printf '\n==> %s\n' "$1"; }

say "1/4 repository state"
echo "HEAD   : $(git log --oneline -1)"
echo "branch : $(git rev-parse --abbrev-ref HEAD)"
if ! git merge-base --is-ancestor c511fb6 HEAD 2>/dev/null; then
  echo "WARNING: this checkout predates c511fb6; fetch the session branch first:" >&2
  echo "  git fetch origin $BRANCH && git reset --hard FETCH_HEAD" >&2
fi
command -v python3 >/dev/null || { echo "python3 is required" >&2; exit 1; }

say "2/4 dependencies"
python3 - <<'PY' || pip install --break-system-packages -q cryptography Pillow
import cryptography, PIL  # noqa: F401
PY
python3 -c "import cryptography; print('  cryptography', cryptography.__version__)"
python3 -c "import PIL; print('  Pillow', PIL.__version__)"

say "3/4 unsigned APK (from the git blob the CI produced)"
mkdir -p artifacts/unsigned
if [ -f artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk ] &&
   [ "$(sha256sum artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk | cut -d' ' -f1)" = "$UNSIGNED_SHA" ]; then
  echo "  already present and correct"
else
  git fetch -q origin "$UNSIGNED_BLOB"
  git cat-file -p "$UNSIGNED_BLOB" > artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk
  got="$(sha256sum artifacts/unsigned/Manager-6.0.0-UNSIGNED.apk | cut -d' ' -f1)"
  [ "$got" = "$UNSIGNED_SHA" ] || { echo "sha256 mismatch: $got" >&2; exit 1; }
  echo "  restored, sha256 verified"
fi

say "4/4 signing material and archive"
if [ -d "$STAGE/Manager-6.1-Themes/signing-keys" ]; then
  echo "  found an extracted bundle in $STAGE"
  python3 build-kit/scripts/apk_v2_sign.py verify \
    "$STAGE/Manager-6.1-Themes/Synthetica-Manager-6.1-Themes-SIGNED.apk"
else
  cat <<'EOF'
  The signing key and the signed APK are NOT in git on purpose, so they cannot be
  restored from here. They live in Drive:

    SYNTHETICA/Synthetica-Manager-6.1-Themes/
      Manager-6.1-Themes.zip                    (everything: key, APKs, docs)
      Synthetica-Manager-6.1-Themes-SIGNED.apk  (just the APK)
      MANIFEST.txt                              (sha256 + certificate fingerprint)

  Download the zip, unpack it, then re-run:

      ./build-kit/scripts/restore_session.sh <unpacked-dir>

  That verifies the APK signature and checks the key opens with PASSWORD.txt.
EOF
  exit 0
fi

echo
echo "Restore complete."
