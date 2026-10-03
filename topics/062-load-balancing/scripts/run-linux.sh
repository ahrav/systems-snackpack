#!/bin/sh
set -eu
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_TARGET
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
    printf '%s\n' 'flags: RUSTFLAGS, CARGO_ENCODED_RUSTFLAGS and CARGO_BUILD_TARGET unset; remaining Cargo environment below; effective rustc flags recorded in codegen.txt'
    env | LC_ALL=C sort | sed -n '/^CARGO_/p'
} > evidence/host.txt
cargo test --offline -p topic062-load-balancing > evidence/tests.txt 2>&1
cargo run --offline --release -p topic062-load-balancing --example contracts > evidence/example.txt 2>&1
cargo clean --offline --release -p topic062-load-balancing > evidence/codegen.txt 2>&1
cargo rustc -v --offline --release -p topic062-load-balancing --lib -- --emit=asm >> evidence/codegen.txt 2>&1
# Cargo single-quotes the directory when the path has a space.
out_dir=$(sed -n "/--crate-name topic062_load_balancing /{s/.*--out-dir '\([^']*\)'.*/\1/p;t;s/.*--out-dir \([^ ]*\).*/\1/p}" evidence/codegen.txt)
set -- "$out_dir"/topic062_load_balancing-*.s
test "$#" -eq 1
test -f "$1"
cp "$1" evidence/contracts.s
test -s evidence/contracts.s
sha256sum topics/062-load-balancing/src/lib.rs topics/062-load-balancing/examples/contracts.rs topics/062-load-balancing/scripts/run-linux.sh > evidence/source-files.sha256
sha256sum evidence/host.txt evidence/tests.txt evidence/example.txt evidence/codegen.txt evidence/contracts.s evidence/source-files.sha256 > evidence/SHA256SUMS
cat evidence/example.txt
