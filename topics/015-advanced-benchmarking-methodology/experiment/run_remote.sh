#!/usr/bin/env bash
set -euo pipefail

if (($# != 2)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd)"
output_dir="$2"
topic_rel="topics/015-advanced-benchmarking-methodology"
topic_dir="$repo_root/$topic_rel"
gates_dir="$output_dir/gates"

mkdir -p "$gates_dir"

{
    date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    lscpu
    rustc -vV
    cargo -V
    cc --version
    rustc --print cfg -C target-cpu=native
} >"$output_dir/host.txt" 2>&1

printf '%s\n' \
    "workspace_gates=compiler defaults" \
    "focused_build=--release -C target-cpu=native -C codegen-units=1" \
    "focused_affinity=taskset -c 0" \
    "source_commit=${SOURCE_COMMIT:-unknown}" \
    "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
    >"$output_dir/build-flags.txt"

(
    cd "$repo_root"
    rg --files "$topic_rel" | sort | xargs sha256sum
) >"$output_dir/source-files.sha256"

(
    cd "$repo_root"
    cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    cargo clippy --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    cargo bench --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1

(
    cd "$repo_root"
    RUSTFLAGS="-C target-cpu=native -C codegen-units=1" \
        cargo build --release \
        -p advanced-benchmarking-methodology \
        --example order_bias
) >"$output_dir/native-build.log" 2>&1

binary="$repo_root/target/release/examples/order_bias"
sha256sum "$binary" >"$output_dir/order_bias.sha256"
nm -C "$binary" >"$output_dir/order_bias.symbols.txt"

"$topic_dir/experiment/run_processes.sh" \
    "$binary" \
    "$output_dir/raw.csv" \
    "$output_dir/summary.csv" \
    12 \
    0 \
    >"$output_dir/process.log" 2>&1

objdump -d -C "$binary" >"$output_dir/codegen-full.txt"
rg -n -C 16 "advanced_benchmarking_methodology::checksum" \
    "$output_dir/codegen-full.txt" \
    >"$output_dir/codegen-checksum.txt"
gzip -9 "$output_dir/codegen-full.txt"

(
    cd "$output_dir"
    rg --files . |
        sort |
        rg -v '^\./evidence\.sha256$' |
        xargs sha256sum
) >"$output_dir/evidence.sha256"
