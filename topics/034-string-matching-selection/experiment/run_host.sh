#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256" >&2
    exit 2
fi

output_dir=$1
source_commit=$2
source_archive_sha256=$3

if [[ -e "$output_dir" ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
work_dir="${output_dir}.work"
if [[ -e "$work_dir" ]]; then
    echo "work directory already exists: $work_dir" >&2
    exit 2
fi

mkdir -p "$output_dir" "$work_dir"
generic_target="$work_dir/generic-target"
native_target="$work_dir/native-target"

write_source_manifest() {
    local destination=$1
    (
        cd "$repo_root"
        rg --files --hidden -g '!target/**' -g '!.git/**' -0 |
            LC_ALL=C sort -z |
            xargs -0 sha256sum
    ) >"$destination"
}

record_optional() {
    local name=$1
    shift
    {
        echo "COMMAND=$*"
        "$@"
    } >"$output_dir/$name" 2>&1 || true
}

run_gate() {
    local name=$1
    shift
    {
        echo "COMMAND=$*"
        "$@"
    } >"$output_dir/$name" 2>&1
}

{
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "repository_root=$repo_root"
    echo "host_runner=topics/034-string-matching-selection/experiment/run_host.sh"
} >"$output_dir/source_identity.txt"

{
    echo "ssh_target=${SSH_TARGET_LABEL:-not-recorded-by-caller}"
    echo "resolved_hostname=$(hostname -f)"
    echo "uname_a=$(uname -a)"
    echo "architecture=$(uname -m)"
    echo "kernel=$(uname -r)"
    echo "available_cpu_count=$(nproc)"
    echo "shell=$BASH_VERSION"
    echo "generic_flags=baseline target; no RUSTFLAGS"
    echo "native_flags=-C target-cpu=native -C debuginfo=1"
} >"$output_dir/host.txt"

lscpu >"$output_dir/lscpu.txt" 2>&1
nproc --all >"$output_dir/nproc_all.txt" 2>&1
taskset -pc $$ >"$output_dir/affinity.txt" 2>&1
rustc -Vv >"$output_dir/rustc.txt" 2>&1
cargo -V >"$output_dir/cargo.txt" 2>&1
rustc --print target-features >"$output_dir/rust_target_features.txt" 2>&1
record_optional gcc.txt gcc --version
record_optional cc.txt cc --version
record_optional clang.txt clang --version
record_optional objdump.txt objdump --version
record_optional nm.txt nm --version
record_optional rustup.txt rustup show active-toolchain
env | LC_ALL=C sort | rg '^(CARGO|CC|CFLAGS|PATH|RUST)' >"$output_dir/build_environment.txt" || true

write_source_manifest "$output_dir/source_manifest.before.sha256"

cd "$repo_root"

run_gate fmt.log cargo fmt --all -- --check
run_gate test_lib_examples.log env CARGO_TARGET_DIR="$generic_target" \
    cargo test --locked --workspace --lib --examples
run_gate test_doc.log env CARGO_TARGET_DIR="$generic_target" \
    cargo test --locked --workspace --doc
run_gate clippy.log env CARGO_TARGET_DIR="$generic_target" \
    cargo clippy --locked --workspace --all-targets -- -D warnings
run_gate bench_build.log env CARGO_TARGET_DIR="$generic_target" \
    cargo bench --locked --workspace --no-run
run_gate doc_build.log env CARGO_TARGET_DIR="$generic_target" RUSTDOCFLAGS='-D warnings' \
    cargo doc --locked --workspace --no-deps

run_gate generic_build.log env CARGO_TARGET_DIR="$generic_target" \
    cargo build --locked --release --package string-matching-selection \
    --bin string-match-probe
generic_binary="$generic_target/release/string-match-probe"
run_gate generic_verify.log "$generic_binary" verify
sha256sum "$generic_binary" >"$output_dir/generic_binary.sha256"

run_gate native_build.log env CARGO_TARGET_DIR="$native_target" \
    RUSTFLAGS='-C target-cpu=native -C debuginfo=1' \
    cargo build --locked --release --package string-matching-selection \
    --bin string-match-probe
native_binary="$native_target/release/string-match-probe"
run_gate native_verify.log "$native_binary" verify
sha256sum "$native_binary" >"$output_dir/native_binary.sha256"

python3 -I topics/034-string-matching-selection/experiment/run_processes.py \
    --binary "$native_binary" \
    --output "$output_dir/benchmark" \
    --blocks 12 \
    --aa-blocks 4 \
    --seed 340034 \
    --target-ms 200 >"$output_dir/benchmark_runner.log" 2>&1

python3 -I topics/034-string-matching-selection/experiment/validate_receipts.py \
    "$output_dir/benchmark" >"$output_dir/receipt_validation.log" 2>&1

nm -n "$native_binary" |
    rg 'topic034_(left_to_right|kmp|horspool)_find' >"$output_dir/symbols.txt"
for symbol in \
    topic034_left_to_right_find \
    topic034_kmp_find \
    topic034_horspool_find
do
    objdump -d --no-show-raw-insn --disassemble="$symbol" "$native_binary" \
        >"$output_dir/${symbol}.asm"
    rg -q "<$symbol>" "$output_dir/${symbol}.asm"
done
sha256sum "$output_dir"/*.asm >"$output_dir/disassembly.sha256"

write_source_manifest "$output_dir/source_manifest.after.sha256"
cmp "$output_dir/source_manifest.before.sha256" "$output_dir/source_manifest.after.sha256"

manifest_temp="$work_dir/SHA256SUMS"
(
    cd "$output_dir"
    rg --files -0 |
        LC_ALL=C sort -z |
        xargs -0 sha256sum
) >"$manifest_temp"
cp "$manifest_temp" "$output_dir/SHA256SUMS"

{
    echo "CHECK=PASS"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "benchmark_blocks=12"
    echo "aa_blocks=4"
    echo "timing_binary_sha256=$(sha256sum "$native_binary" | awk '{print $1}')"
} >"$output_dir/run.status"

echo "CHECK=PASS output=$output_dir"
