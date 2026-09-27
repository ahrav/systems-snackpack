#!/bin/sh
# Run from the extracted archive root containing this topic and workspace files.
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
    printf '%s\n' 'flags: Cargo defaults; release opt-level=3; default target CPU; RUSTFLAGS unset'
    env | LC_ALL=C sort | sed -n '/^RUSTFLAGS=/p; /^CARGO_ENCODED_RUSTFLAGS=/p'
} > evidence/host.txt
unset RUSTFLAGS CARGO_ENCODED_RUSTFLAGS
cargo test --offline -p topic060-deterministic-simulation > evidence/tests.txt 2>&1
cargo run --offline --release -p topic060-deterministic-simulation --example explore > evidence/example.txt 2>&1
cargo rustc --offline --release -p topic060-deterministic-simulation --lib -- --emit=asm > evidence/codegen.txt 2>&1
find target/release/deps -name 'topic060_deterministic_simulation-*.s' -exec cp '{}' evidence/search.s \;
test -s evidence/search.s
sha256sum topics/060-deterministic-simulation/src/lib.rs topics/060-deterministic-simulation/examples/explore.rs topics/060-deterministic-simulation/scripts/run-linux.sh > evidence/source-files.sha256
sha256sum evidence/host.txt evidence/tests.txt evidence/example.txt evidence/codegen.txt evidence/search.s evidence/source-files.sha256 > evidence/SHA256SUMS
cat evidence/example.txt
cat evidence/SHA256SUMS
