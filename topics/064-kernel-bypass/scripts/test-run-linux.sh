#!/bin/sh
# Run this test from the repository root.
set -eu
root=$(pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/topics"
cp Cargo.toml Cargo.lock rust-toolchain.toml "$work/"
cp -R topics/064-kernel-bypass "$work/topics/"
cd "$work"
runner=topics/064-kernel-bypass/scripts/run-linux.sh

sh "$runner" > /dev/null 2>&1 || { echo "FAIL: fresh run exited non-zero"; exit 1; }
[ -s evidence/contracts.s ] || { echo "FAIL: fresh run produced no evidence/contracts.s"; exit 1; }

# A second .s from an earlier build makes the copy source ambiguous.
printf 'stale\n' > target/release/deps/topic064_kernel_bypass-0000000000stale.s
if sh "$runner" > /dev/null 2>&1; then
    echo "FAIL: runner exited 0 with two candidate .s files"
    exit 1
fi
echo "PASS: $root/$runner rejects ambiguous assembly candidates"
