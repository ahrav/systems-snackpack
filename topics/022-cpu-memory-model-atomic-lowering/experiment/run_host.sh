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

# When cargo on PATH is a standalone binary rather than the rustup shim, the
# repository's rust-toolchain.toml pin is silently ignored and a host-default
# compiler changes the measured code generation. Fail closed on a mismatch.
# Resolve from the workspace: rustup selects the toolchain by cwd, so probing
# from the caller's directory could report a different compiler than the one
# the builds below use.
if [[ -f "$workspace/rust-toolchain.toml" ]]; then
    pinned_toolchain=$(sed -n 's/^channel = "\(.*\)"$/\1/p' "$workspace/rust-toolchain.toml")
    resolved_rustc=$(cd "$workspace" && rustc --version | awk '{print $2}')
    if [[ -z "$pinned_toolchain" || "$resolved_rustc" != "$pinned_toolchain" ]]; then
        printf 'resolved rustc %s does not match the pinned toolchain %s\n' \
            "$resolved_rustc" "${pinned_toolchain:-unparsed}" >&2
        exit 2
    fi
fi

# Caller build overrides would silently change the measured binaries: for
# example CARGO_ENCODED_RUSTFLAGS takes precedence over the inline RUSTFLAGS
# below and CARGO_BUILD_TARGET moves the artifacts the later cp expects.
unset CARGO_BUILD_RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_TARGET_DIR CARGO_BUILD_TARGET
unset RUSTC RUSTC_WRAPPER RUSTDOC RUSTDOCFLAGS RUSTFLAGS
unset LD_LIBRARY_PATH LD_PRELOAD

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

# Run the direct rustc invocations from the workspace: rustup resolves the
# toolchain from the working directory, and these must use the same pinned
# compiler as the Cargo builds above.
(
    cd "$workspace"
    rustc --edition=2024 --crate-type=lib -O -C target-cpu=native \
        "$topic_dir/src/lib.rs" --emit=asm -o "$output/codegen/lowering-native.s"
    rustc --edition=2024 --crate-type=lib -O -C target-cpu=generic \
        "$topic_dir/src/lib.rs" --emit=asm -o "$output/codegen/lowering-generic.s"
    rustc --edition=2024 -O -C target-cpu=generic \
        "$topic_dir/src/bin/store_buffering.rs" -o "$output/binaries/store-buffering-generic"
)

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

# Provenance covers the source, experiment, and documentation inputs only;
# retained measurement receipts from earlier runs must not affect the hash of
# the source being tested. Hash repo-relative paths from the workspace and
# include the workspace-level build inputs the measured binaries consume.
(
    cd "$workspace"
    topic_rel=${topic_dir#"$workspace"/}
    {
        rg --files "$topic_rel" -g '!**/measurements/**'
        printf '%s\n' Cargo.toml Cargo.lock rust-toolchain.toml
    } | sort | xargs sha256sum
) > "$output/source-files.sha256"
# Seal every retained receipt: hash everything in the output directory except
# the manifest itself, so edits to host, correctness, codegen, or provenance
# files are detectable outside this Git commit.
(
    cd "$output"
    rg --files -uu -g '!evidence.sha256' . | sort | xargs sha256sum
) > "$output/evidence.sha256"
