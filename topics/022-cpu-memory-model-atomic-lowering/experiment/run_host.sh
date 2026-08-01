#!/usr/bin/env bash
set -euo pipefail

topic_dir=$(cd "$(dirname "$0")/.." && pwd)
workspace=$(cd "$topic_dir/../.." && pwd)
output=${1:?usage: run_host.sh OUTPUT_DIRECTORY}
cost_cpu=${COST_CPU:-3}
worker_cpu0=${WORKER_CPU0:-0}
worker_cpu1=${WORKER_CPU1:-1}
coordinator_cpu=${COORDINATOR_CPU:-2}
litmus_iterations=${LITMUS_ITERATIONS:-1000000}

test ! -e "$output"
mkdir -p "$output/binaries" "$output/codegen" "$output/correctness" "$output/litmus"
build_root=$(mktemp -d /tmp/topic22-build.XXXXXXXX)
trap 'rm -rf -- "$build_root"' EXIT

{
    printf 'captured_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'host_argument=%s\n' "${HOST_ARGUMENT:-unspecified}"
    printf 'resolved_hostname='; hostname -f 2>/dev/null || hostname
    printf 'uname='; uname -a
    printf 'cpu_count='; getconf _NPROCESSORS_ONLN
    lscpu
    rustc -vV
    cargo --version
    cc --version | head -n 1
    rustc --print cfg -C target-cpu=native | rg '^target_feature'
    printf 'cost_cpu=%s\n' "$cost_cpu"
    printf 'litmus_cpus=%s,%s,%s\n' "$worker_cpu0" "$worker_cpu1" "$coordinator_cpu"
} > "$output/host.txt"

(
    cd "$workspace"
    cargo test -p cpu-memory-model-atomic-lowering --lib --bins --examples
    cargo run --release -p cpu-memory-model-atomic-lowering --example publication -- 100000
) > "$output/correctness/output.txt" 2> "$output/correctness/stderr.txt"

target_dir="$build_root/target-native"
(
    cd "$workspace"
    CARGO_TARGET_DIR="$target_dir" RUSTFLAGS='-C target-cpu=native' \
        cargo build --release -p cpu-memory-model-atomic-lowering --bins
)

rustc --edition=2024 --crate-type=lib -O -C target-cpu=native \
    "$topic_dir/src/lib.rs" --emit=asm -o "$output/codegen/lowering-native.s"
rustc --edition=2024 --crate-type=lib -O -C target-cpu=generic \
    "$topic_dir/src/lib.rs" --emit=asm -o "$output/codegen/lowering-generic.s"
rustc --edition=2024 -O -C target-cpu=generic \
    "$topic_dir/src/bin/store_buffering.rs" -o "$output/binaries/store-buffering-generic"

cp "$target_dir/release/atomic-cost" "$output/binaries/atomic-cost-native"
cp "$target_dir/release/store-buffering" "$output/binaries/store-buffering-native"
cost_binary="$output/binaries/atomic-cost-native"
litmus_native="$output/binaries/store-buffering-native"
python3 "$topic_dir/experiment/run_processes.py" \
    "$cost_binary" "$output/processes" --cpu "$cost_cpu"

for mode in relaxed release-acquire seqcst; do
    "$litmus_native" "$mode" "$litmus_iterations" \
        "$worker_cpu0" "$worker_cpu1" "$coordinator_cpu"
done > "$output/litmus/native.txt"
for mode in relaxed release-acquire seqcst; do
    "$output/binaries/store-buffering-generic" "$mode" "$litmus_iterations" \
        "$worker_cpu0" "$worker_cpu1" "$coordinator_cpu"
done > "$output/litmus/generic.txt"

objdump -drwC "$cost_binary" > "$output/codegen/atomic-cost.objdump.txt"
objdump -drwC "$litmus_native" > "$output/codegen/store-buffering.objdump.txt"

rg --files "$topic_dir" | sort | xargs sha256sum > "$output/source-files.sha256"
sha256sum "$cost_binary" "$litmus_native" "$output/binaries/store-buffering-generic" \
    "$output/processes/raw.csv" "$output/processes/summary.json" \
    "$output/litmus/native.txt" "$output/litmus/generic.txt" \
    "$output/codegen/lowering-native.s" "$output/codegen/lowering-generic.s" \
    > "$output/evidence.sha256"
