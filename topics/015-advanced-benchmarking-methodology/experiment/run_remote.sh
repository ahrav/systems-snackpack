#!/usr/bin/env bash
set -euo pipefail

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd)"
output_dir="$2"
topic_rel="topics/015-advanced-benchmarking-methodology"
topic_dir="$repo_root/$topic_rel"
gates_dir="$output_dir/gates"
cpu="${3:-0}"

mkdir -p "$gates_dir"

# The focused build goes to a private directory so the measured artifact is
# never a stale binary from an earlier build and never disappears into a
# caller-configured CARGO_TARGET_DIR. It is not evidence, so it stays outside
# the output tree that evidence.sha256 walks.
build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT

if ! command -v taskset >/dev/null 2>&1; then
    printf 'taskset is required for remote evidence collection\n' >&2
    exit 2
fi

# The captured host record must not leak the machine identity into shared
# evidence; every occurrence of the local hostname is replaced before writing.
host_name="$(uname -n)"
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
} 2>&1 | sed "s/${host_name}/redacted-host/g" >"$output_dir/host.txt"

# One definition feeds both the provenance record and the build so the
# recorded flags cannot diverge from the flags the measured binary used.
native_rustflags="-C target-cpu=native -C codegen-units=1"

printf '%s\n' \
    "workspace_gates=compiler defaults" \
    "focused_build=--release ${native_rustflags}" \
    "focused_affinity_requested=taskset -c ${cpu}" \
    "source_commit=${SOURCE_COMMIT:-unknown}" \
    "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
    >"$output_dir/build-flags.txt"

# The measured binary is determined by more than the topic directory: the
# package inherits edition, rust-version, and lints from the root manifest, the
# lockfile pins the dependency graph, the toolchain file pins the compiler, and
# Cargo configuration can inject build flags. Hashing only the topic would let
# an identical manifest accompany a differently built binary.
(
    cd "$repo_root"
    {
        rg --files "$topic_rel"
        for input in \
            Cargo.toml \
            Cargo.lock \
            rust-toolchain.toml \
            rust-toolchain \
            .cargo/config.toml \
            .cargo/config; do
            if [[ -f "$input" ]]; then
                printf '%s\n' "$input"
            fi
        done
    } | sort -u | xargs sha256sum
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
    RUSTFLAGS="$native_rustflags" \
        cargo build --release \
        --target-dir "$build_dir" \
        -p advanced-benchmarking-methodology \
        --example order_bias
) >"$output_dir/native-build.log" 2>&1

# --target-dir outranks both CARGO_TARGET_DIR and build.target-dir, so this path
# is the artifact Cargo just emitted rather than whatever the repository's
# default target directory happens to hold.
binary="$build_dir/release/examples/order_bias"
if [[ ! -x "$binary" ]]; then
    printf 'focused build did not produce %s\n' "$binary" >&2
    exit 1
fi
# The digest is recorded against the artifact name because the build directory
# is ephemeral; including its path would make identical binaries produce
# different-looking evidence between runs.
(cd -- "$(dirname -- "$binary")" && sha256sum "$(basename -- "$binary")") \
    >"$output_dir/order_bias.sha256"
nm -C "$binary" >"$output_dir/order_bias.symbols.txt"

"$topic_dir/experiment/run_processes.sh" \
    "$binary" \
    "$output_dir/raw.csv" \
    "$output_dir/summary.csv" \
    12 \
    "$cpu" \
    >"$output_dir/process.log" 2>&1

# The runner resolves and probes its own CPU, so the branch it reports is the
# only record of the affinity that actually applied. Affinity is part of this
# evidence claim, so an unpinned run is a failed collection, not a footnote.
resolved_affinity="$(sed -n 's/^affinity=//p' "$output_dir/process.log" | tail -1)"
if [[ -z "$resolved_affinity" ]]; then
    printf 'run_processes.sh did not report an affinity branch\n' >&2
    exit 1
fi
if [[ "$resolved_affinity" == "none" ]]; then
    printf 'affinity is required for this evidence run; runner reported none\n' >&2
    exit 1
fi
printf 'focused_affinity_actual=%s\n' "$resolved_affinity" \
    >"$output_dir/affinity-resolved.txt"

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
