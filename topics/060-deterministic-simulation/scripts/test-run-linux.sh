#!/bin/sh
# Run this test from the repository root.
set -eu
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/topics"
cp Cargo.toml Cargo.lock "$work/"
cp -R topics/060-deterministic-simulation "$work/topics/"
cd "$work"
runner=topics/060-deterministic-simulation/scripts/run-linux.sh

sh "$runner" > /dev/null 2>&1 || { echo "FAIL: fresh run exited non-zero"; exit 1; }
[ -s evidence/search.s ] || { echo "FAIL: fresh run produced no evidence/search.s"; exit 1; }

# A second .s from an earlier build makes the copy source ambiguous.
printf 'stale\n' > target/release/deps/topic060_deterministic_simulation-0000000000stale.s
if sh "$runner" > /dev/null 2>&1; then
    echo "FAIL: runner exited 0 with two candidate .s files"
    exit 1
fi
echo "PASS: $root/$runner rejects ambiguous assembly candidates"
