#!/bin/sh
set -eu
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
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
cargo test --offline -p topic061-probabilistic-filters > evidence/tests.txt 2>&1
cargo run --offline --release -p topic061-probabilistic-filters --example contracts > evidence/example.txt 2>&1
cargo rustc --offline --release -p topic061-probabilistic-filters --lib -- --emit=asm > evidence/codegen.txt 2>&1
find target/release/deps -name 'topic061_probabilistic_filters-*.s' -exec cp '{}' evidence/contracts.s \;
test -s evidence/contracts.s
sha256sum topics/061-probabilistic-filters/src/lib.rs topics/061-probabilistic-filters/examples/contracts.rs topics/061-probabilistic-filters/scripts/run-linux.sh > evidence/source-files.sha256
sha256sum evidence/host.txt evidence/tests.txt evidence/example.txt evidence/codegen.txt evidence/contracts.s evidence/source-files.sha256 > evidence/SHA256SUMS
cat evidence/example.txt
