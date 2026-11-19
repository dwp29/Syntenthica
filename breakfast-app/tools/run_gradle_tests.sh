#!/usr/bin/env bash
# Run the JVM unit tests and leave readable evidence behind.
#
# CI logs are not always reachable, so the output and the JUnit XML are written
# into ci-stage/breakfast/ where they can be read from the repository. The script
# exits non-zero when the tests fail, and the workflow's later steps refuse to
# build or keep an APK when evidence is missing.
set -euo pipefail
cd "$(dirname "$0")/.."

OUT="../ci-stage/breakfast"
# Remove the previous run's evidence first, including the pass marker. Without
# this, a stale TESTS-PASSED would let a later failing run still build an APK:
# the gate would be satisfied by a file from a different, successful run.
rm -f "$OUT/BREAKFAST-manager.apk" "$OUT/APK-SHA256.txt" "$OUT/APK-BADGING.txt" \
      "$OUT/TESTS-PASSED" "$OUT"/TEST-*.xml
mkdir -p "$OUT"

set +e
# bash, not sh: PIPESTATUS does not exist in dash, and without it a failed
# Gradle run inside a pipe looks like success - which is exactly the bug this
# script exists to prevent.
./gradlew :app:testDebugUnitTest --no-daemon --stacktrace 2>&1 | tee "$OUT/TEST-LOG.txt"
STATUS=${PIPESTATUS[0]}
set -e

find app/build/test-results -name '*.xml' -exec cp {} "$OUT/" \; 2>/dev/null || true

if [ "$STATUS" -ne 0 ]; then
  echo "unit tests failed with status $STATUS"
  exit "$STATUS"
fi

python3 tools/check_test_results.py
touch "$OUT/TESTS-PASSED"
echo "evidence written to $OUT"
