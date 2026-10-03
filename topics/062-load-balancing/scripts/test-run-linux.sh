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

# A second .s from an earlier build makes the copy source ambiguous.
printf 'stale\n' > target/release/deps/topic062_load_balancing-0000000000stale.s
if sh "$runner" > /dev/null 2>&1; then
    echo "FAIL: runner exited 0 with two candidate .s files"
    exit 1
fi

# Receipts record the effective optimization level when CARGO_PROFILE_RELEASE_OPT_LEVEL overrides the default.
rm -rf target evidence
CARGO_PROFILE_RELEASE_OPT_LEVEL=1 sh "$runner" > /dev/null 2>&1 || { echo "FAIL: override run exited non-zero"; exit 1; }
grep -q -- '-C opt-level=1' evidence/codegen.txt || { echo "FAIL: codegen.txt does not record the overridden opt-level"; exit 1; }
grep -q '^CARGO_PROFILE_RELEASE_OPT_LEVEL=1$' evidence/host.txt || { echo "FAIL: host.txt does not record the Cargo override"; exit 1; }
echo "PASS: $root/$runner rejects ambiguous assembly candidates and records effective build flags"
