#!/bin/sh
# Run this test from the repository root.
set -eu
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/topics"
cp Cargo.toml Cargo.lock "$work/"
cp -R topics/062-load-balancing "$work/topics/"
cd "$work"
runner=topics/062-load-balancing/scripts/run-linux.sh

sh "$runner" > /dev/null 2>&1 || { echo "FAIL: fresh run exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: fresh run produced no evidence/contracts.s"; exit 1; }
grep -q -- '-C opt-level=3' evidence/codegen.txt || { echo "FAIL: codegen.txt does not record the effective opt-level"; exit 1; }

# The per-package clean removes a stale .s from an earlier build and forces a rebuild that records rustc flags.
printf 'stale\n' > target/release/deps/topic062_load_balancing-0000000000stale.s
sh "$runner" > /dev/null 2>&1 || { echo "FAIL: rerun with a stale .s exited non-zero"; exit 1; }
grep -q -- '-C opt-level=3' evidence/codegen.txt || { echo "FAIL: rerun codegen.txt lost the rustc invocation (Fresh unit)"; exit 1; }
! grep -q '^stale$' evidence/contracts.s || { echo "FAIL: stale assembly copied into evidence"; exit 1; }
set -- target/release/deps/topic062_load_balancing-*.s
[ "$#" -eq 1 ] || { echo "FAIL: $# candidate .s files remain after the run"; exit 1; }

# The runner pins its own target directory, so the assembly it inspects comes from the build it ran.
CARGO_TARGET_DIR=$work/other sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with caller CARGO_TARGET_DIR exited non-zero"; exit 1; }
[ ! -d "$work/other" ] || { echo "FAIL: caller CARGO_TARGET_DIR was used for the build"; exit 1; }
grep -q "^CARGO_TARGET_DIR=$work/target\$" evidence/host.txt || { echo "FAIL: host.txt does not record the pinned target dir"; exit 1; }

# The runner builds for the host; a caller's CARGO_BUILD_TARGET keeps artifacts out of target/<triple>/.
rm -rf target evidence
CARGO_BUILD_TARGET=$(rustc -vV | sed -n 's/^host: //p') sh "$runner" > /dev/null 2>&1 || { echo "FAIL: run with caller CARGO_BUILD_TARGET exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: CARGO_BUILD_TARGET run produced no evidence/contracts.s"; exit 1; }

# Receipts record the effective optimization level when CARGO_PROFILE_RELEASE_OPT_LEVEL overrides the default.
rm -rf target evidence
CARGO_PROFILE_RELEASE_OPT_LEVEL=1 sh "$runner" > /dev/null 2>&1 || { echo "FAIL: override run exited non-zero"; exit 1; }
grep -q -- '-C opt-level=1' evidence/codegen.txt || { echo "FAIL: codegen.txt does not record the overridden opt-level"; exit 1; }
grep -q '^CARGO_PROFILE_RELEASE_OPT_LEVEL=1$' evidence/host.txt || { echo "FAIL: host.txt does not record the Cargo override"; exit 1; }
echo "PASS: $root/$runner rebuilds codegen each run, pins its target dir and host target, and records effective build flags"
