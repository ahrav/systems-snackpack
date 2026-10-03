#!/bin/sh
set -eu
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
mkdir -p evidence
{
    hostname
    uname -a
    nproc
    lscpu
    sed -n '1,32p' /proc/cpuinfo
    rustc -Vv
    cargo -V
    rustc --print cfg
    printf '%s\n' 'flags: Cargo defaults; release opt-level=3; default target CPU; RUSTFLAGS unset'
} > evidence/host.txt
cargo test --offline -p topic064-kernel-bypass > evidence/tests.txt 2>&1
cargo run --offline --release -p topic064-kernel-bypass --example contracts > evidence/example.txt 2>&1
cargo rustc --offline --release -p topic064-kernel-bypass --lib -- --emit=asm > evidence/codegen.txt 2>&1
set -- target/release/deps/topic064_kernel_bypass-*.s
test "$#" -eq 1
test -f "$1"
cp "$1" evidence/contracts.s
test -s evidence/contracts.s
sha256sum topics/064-kernel-bypass/src/lib.rs topics/064-kernel-bypass/examples/contracts.rs topics/064-kernel-bypass/scripts/run-linux.sh > evidence/source-files.sha256
sha256sum evidence/host.txt evidence/tests.txt evidence/example.txt evidence/codegen.txt evidence/contracts.s evidence/source-files.sha256 > evidence/SHA256SUMS
cat evidence/example.txt
