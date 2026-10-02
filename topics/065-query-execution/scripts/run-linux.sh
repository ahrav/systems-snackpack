#!/bin/sh
set -eu
unset CARGO_ENCODED_RUSTFLAGS
export RUSTFLAGS='-C target-cpu=native'
mkdir -p evidence
{
    hostname
    uname -a
    nproc
    lscpu
    sed -n '1,32p' /proc/cpuinfo
    rustc -Vv
    cargo -V
    rustc --print cfg -C target-cpu=native
    printf '%s\n' 'flags: release opt-level=3; -C target-cpu=native; LTO off; default codegen units'
} > evidence/host.txt
cargo test --offline -p topic065-query-execution > evidence/tests.txt 2>&1
cargo build --offline --release -p topic065-query-execution --example probe > evidence/build.txt 2>&1
cargo rustc --offline --release -p topic065-query-execution --lib -- --emit=asm > evidence/codegen.txt 2>&1
find target/release/deps -name 'topic065_query_execution-*.s' -exec cp '{}' evidence/query.s \;
test -s evidence/query.s
objdump -d target/release/examples/probe > evidence/linked-code.txt
python3 topics/065-query-execution/scripts/measure.py "${1:-final}" > evidence/measurement.txt
sha256sum Cargo.toml Cargo.lock topics/065-query-execution/Cargo.toml topics/065-query-execution/src/lib.rs topics/065-query-execution/examples/probe.rs topics/065-query-execution/scripts/* > evidence/source-files.sha256
sha256sum target/release/examples/probe > evidence/binary.sha256
find evidence -type f ! -name SHA256SUMS -print | sort | xargs sha256sum > evidence/SHA256SUMS
cat evidence/measurement.txt
