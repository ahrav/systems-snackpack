#!/bin/sh
set -eu
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET
export CARGO_TARGET_DIR="$PWD/target"
rm -rf evidence
mkdir evidence
{
    hostname
    uname -a
    nproc
    lscpu
    sed -n '1,32p' /proc/cpuinfo
    rustc -Vv
    cargo -V
    rustc --print cfg
    printf '%s\n' 'flags: RUSTFLAGS, CARGO_ENCODED_RUSTFLAGS, CARGO_BUILD_RUSTFLAGS and CARGO_BUILD_TARGET unset; remaining Cargo environment below; effective rustc flags recorded in codegen.txt'
    env | LC_ALL=C sort | sed -n '/^CARGO_/p'
} > evidence/host.txt
cargo test --offline -p topic064-kernel-bypass > evidence/tests.txt 2>&1
cargo run --offline --release -p topic064-kernel-bypass --example contracts > evidence/example.txt 2>&1
# Start codegen from an empty target directory: every layout is gone, so the rebuilt unit is the only candidate.
rm -rf "$CARGO_TARGET_DIR"
cargo rustc -v --offline --release -p topic064-kernel-bypass --lib -- --emit=asm > evidence/codegen.txt 2>&1
# shellcheck disable=SC2046  # Cargo's relative, hash-named assembly paths contain no whitespace.
set -- $(find target -path '*/release/deps/topic064_kernel_bypass-*.s')
test "$#" -eq 1
test -f "$1"
cp "$1" evidence/contracts.s
test -s evidence/contracts.s
sha256sum topics/064-kernel-bypass/src/lib.rs topics/064-kernel-bypass/examples/contracts.rs topics/064-kernel-bypass/scripts/run-linux.sh > evidence/source-files.sha256
sha256sum evidence/host.txt evidence/tests.txt evidence/example.txt evidence/codegen.txt evidence/contracts.s evidence/source-files.sha256 > evidence/SHA256SUMS
cat evidence/example.txt
