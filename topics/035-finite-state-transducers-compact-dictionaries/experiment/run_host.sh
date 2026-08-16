#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 3 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256" >&2
    exit 2
fi

# Gate redirects and CARGO_TARGET_DIR are evaluated after cd "$repo_root".
output_dir=$(realpath -m -- "$1")
source_commit=$2
source_archive_sha256=$3

: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to the requested alias or literal hostname}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the runtime-resolved backing hostname}"

if [[ ! $source_archive_sha256 =~ ^[0-9a-fA-F]{64}$ ]]; then
    echo "SOURCE_ARCHIVE_SHA256 must contain 64 hexadecimal digits" >&2
    exit 2
fi
if [[ -z $source_commit ]]; then
    echo "SOURCE_COMMIT must not be empty" >&2
    exit 2
fi
if [[ -e $output_dir ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
work_dir="${output_dir}.work"
if [[ -e $work_dir ]]; then
    echo "work directory already exists: $work_dir" >&2
    exit 2
fi

# In-tree output changes the source manifest even when no source file changes.
case "$output_dir/" in
"$repo_root"/*)
    echo "output must live outside the repository: $output_dir" >&2
    exit 2
    ;;
esac

mkdir -p "$output_dir" "$work_dir"
generic_target="$work_dir/generic-target"
native_target="$work_dir/native-target"

# Cargo reads config files from the working directory upward, and settings such
# as build.rustc-wrapper or a linker survive an empty RUSTFLAGS.
refuse_ambient_cargo_config() {
    local search_dir=$1 cargo_config
    while :; do
        for cargo_config in "$search_dir/.cargo/config.toml" "$search_dir/.cargo/config"; do
            if [[ -e $cargo_config ]]; then
                echo "refusing ambient cargo config: $cargo_config" >&2
                exit 2
            fi
        done
        if [[ $search_dir == / ]]; then
            break
        fi
        search_dir=${search_dir%/*}
        search_dir=${search_dir:-/}
    done
}
refuse_ambient_cargo_config "$repo_root"

# $CARGO_HOME/config.toml legitimately carries registry mirrors, so an isolated
# CARGO_HOME bypasses it and its digest is recorded instead of refused.
real_cargo_home=$(realpath -m -- "${CARGO_HOME:-$HOME/.cargo}")
cargo_home="$work_dir/cargo-home"
mkdir -p "$cargo_home"
for cache_entry in registry git; do
    if [[ -e "$real_cargo_home/$cache_entry" ]]; then
        ln -s "$real_cargo_home/$cache_entry" "$cargo_home/$cache_entry"
    fi
done
export CARGO_HOME=$cargo_home
architecture=$(uname -m)
remote_hostname=$(hostname -f)

if [[ $remote_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    echo "resolved host mismatch: expected $SSH_RESOLVED_HOSTNAME, observed $remote_hostname" >&2
    exit 1
fi

case "$SSH_TARGET_LABEL" in
    xxl)
        if [[ $architecture != x86_64 ]]; then
            echo "xxl must resolve to x86_64; observed $architecture" >&2
            exit 1
        fi
        ;;
    dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
        if [[ $architecture != aarch64 && $architecture != arm64 ]]; then
            echo "Arm target must report aarch64 or arm64; observed $architecture" >&2
            exit 1
        fi
        ;;
    *)
        echo "unexpected SSH target label: $SSH_TARGET_LABEL" >&2
        exit 2
        ;;
esac

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

# The caller-supplied commit is otherwise unchecked evidence, and git diff alone
# reports neither a staged change nor a different HEAD.
git_verify=(git -c core.fsmonitor=false -c core.untrackedCache=false -C "$repo_root")
if [[ $("${git_verify[@]}" rev-parse --show-toplevel 2>/dev/null || true) == "$repo_root" ]]; then
    head_commit=$("${git_verify[@]}" rev-parse HEAD)
    if ! expected_commit=$("${git_verify[@]}" rev-parse --verify --quiet "${source_commit}^{commit}"); then
        echo "SOURCE_COMMIT $source_commit is not a commit in this worktree" >&2
        exit 2
    fi
    if [[ $expected_commit != "$head_commit" ]]; then
        echo "worktree HEAD $head_commit does not match SOURCE_COMMIT $expected_commit" >&2
        exit 2
    fi
    if [[ -n $("${git_verify[@]}" status --porcelain) ]]; then
        echo "worktree is not clean; refusing exact-source evidence" >&2
        exit 2
    fi
    source_commit_verified=git-worktree-head-clean
    run_gate git_diff_check.log "${git_verify[@]}" diff --check
else
    source_commit_verified=no-git-worktree-caller-supplied
    {
        echo "CHECK=NOT_APPLICABLE"
        echo "reason=the measured source archive does not contain Git metadata"
    } >"$output_dir/git_diff_check.log"
fi

{
    echo "source_commit=$source_commit"
    echo "source_commit_verified=$source_commit_verified"
    echo "source_archive_sha256=${source_archive_sha256,,}"
    echo "repository_root=$repo_root"
    echo "host_runner=topics/035-finite-state-transducers-compact-dictionaries/experiment/run_host.sh"
} >"$output_dir/source_identity.txt"

{
    echo "ssh_alias=$SSH_TARGET_LABEL"
    echo "configured_hostname=$SSH_RESOLVED_HOSTNAME"
    echo "resolved_remote_hostname=$remote_hostname"
    echo "uname_m=$architecture"
    echo "uname_a=$(uname -a)"
    echo "kernel=$(uname -r)"
    echo "available_cpu_count=$(nproc)"
    echo "configured_cpu_count=$(nproc --all)"
} >"$output_dir/target_resolution.txt"

{
    echo "ssh_target_label=$SSH_TARGET_LABEL"
    echo "ssh_resolved_backing_hostname=$SSH_RESOLVED_HOSTNAME"
    echo "remote_hostname=$remote_hostname"
    echo "uname_a=$(uname -a)"
    echo "architecture=$architecture"
    echo "kernel=$(uname -r)"
    echo "available_cpu_count=$(nproc)"
    echo "configured_cpu_count=$(nproc --all)"
    echo "shell=$BASH_VERSION"
    echo "generic_flags=baseline target; no RUSTFLAGS"
    echo "native_flags=-C target-cpu=native -C debuginfo=1"
} >"$output_dir/host.txt"

lscpu >"$output_dir/lscpu.txt" 2>&1
record_optional lscpu_extended.txt lscpu --extended
record_optional cpuinfo.txt sed -n 1,400p /proc/cpuinfo
nproc --all >"$output_dir/nproc_all.txt" 2>&1
taskset -pc $$ >"$output_dir/affinity.txt" 2>&1
rustc -Vv >"$output_dir/rustc.txt" 2>&1
cargo -V >"$output_dir/cargo.txt" 2>&1
rustc --print target-features >"$output_dir/rust_target_features.txt" 2>&1
rustc --print target-cpus >"$output_dir/rust_target_cpus.txt" 2>&1
rustc --print cfg -C target-cpu=native >"$output_dir/rust_native_cfg.txt" 2>&1
record_optional gcc.txt gcc --version
record_optional cc.txt cc --version
record_optional clang.txt clang --version
record_optional objdump.txt objdump --version
record_optional nm.txt nm --version
record_optional perf.txt perf --version
record_optional rustup.txt rustup show active-toolchain
{
    for name in CARGO_HOME CARGO_TARGET_DIR CC CFLAGS PATH RUSTFLAGS RUSTDOCFLAGS; do
        if value=$(printenv "$name"); then
            printf '%s=%s\n' "$name" "$value"
        fi
    done
} >"$output_dir/build_environment.txt"
{
    printf 'cargo_home_isolated_from=%s\n' "$real_cargo_home"
    for cargo_config in "$real_cargo_home/config.toml" "$real_cargo_home/config"; do
        if [[ -e $cargo_config ]]; then
            sha256sum "$cargo_config"
        fi
    done
} >>"$output_dir/build_environment.txt"

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
    cargo build --locked --release \
    --package finite-state-transducers-compact-dictionaries \
    --bin dictionary-probe
generic_binary="$generic_target/release/dictionary-probe"
run_gate generic_verify.log "$generic_binary" verify
sha256sum "$generic_binary" >"$output_dir/generic_binary.sha256"

run_gate native_build.log env CARGO_TARGET_DIR="$native_target" \
    RUSTFLAGS='-C target-cpu=native -C debuginfo=1' \
    cargo build --locked --release \
    --package finite-state-transducers-compact-dictionaries \
    --bin dictionary-probe
native_binary="$native_target/release/dictionary-probe"
run_gate native_verify.log "$native_binary" verify
sha256sum "$native_binary" >"$output_dir/native_binary.sha256"

python3 -I \
    topics/035-finite-state-transducers-compact-dictionaries/experiment/run_processes.py \
    --binary "$native_binary" \
    --output "$output_dir/benchmark" \
    --blocks 12 \
    --aa-blocks 4 \
    --seed 350035 \
    --target-ms 200 >"$output_dir/benchmark_runner.log" 2>&1

python3 -I \
    topics/035-finite-state-transducers-compact-dictionaries/experiment/validate_receipts.py \
    "$output_dir/benchmark" >"$output_dir/receipt_validation.log" 2>&1

# A missing symbol must reach the count check below, not abort the pipeline.
nm -n "$native_binary" | { rg 'topic035_flat_contains' || true; } >"$output_dir/symbols.txt"
if [[ $(rg -c 'topic035_flat_contains' "$output_dir/symbols.txt" || true) -ne 1 ]]; then
    echo "expected exactly one linked topic035_flat_contains symbol" >&2
    exit 1
fi
objdump -d --no-show-raw-insn --disassemble=topic035_flat_contains "$native_binary" \
    >"$output_dir/topic035_flat_contains.asm"
rg -q '<topic035_flat_contains>' "$output_dir/topic035_flat_contains.asm"
sha256sum "$output_dir/topic035_flat_contains.asm" >"$output_dir/disassembly.sha256"

write_source_manifest "$output_dir/source_manifest.after.sha256"
cmp "$output_dir/source_manifest.before.sha256" "$output_dir/source_manifest.after.sha256"

{
    echo "CHECK=PASS"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=${source_archive_sha256,,}"
    echo "ssh_target_label=$SSH_TARGET_LABEL"
    echo "ssh_resolved_backing_hostname=$SSH_RESOLVED_HOSTNAME"
    echo "remote_hostname=$remote_hostname"
    echo "architecture=$architecture"
    echo "benchmark_blocks=12"
    echo "aa_blocks=4"
    echo "timing_binary_sha256=$(sha256sum "$native_binary" | awk '{print $1}')"
    echo "receipt_validation=$(tr '\n' ' ' <"$output_dir/receipt_validation.log")"
} >"$output_dir/run.status"

manifest_temp="$work_dir/SHA256SUMS"
(
    cd "$output_dir"
    rg --files -0 |
        LC_ALL=C sort -z |
        xargs -0 sha256sum
) >"$manifest_temp"
cp "$manifest_temp" "$output_dir/SHA256SUMS"

echo "CHECK=PASS output=$output_dir"
