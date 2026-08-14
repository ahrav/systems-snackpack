#!/usr/bin/env bash
set -euo pipefail

# The guards precede the function definitions below so compgen sees only
# inherited functions. BASH_ENV runs startup code before this body, and an
# inherited cargo/rustc function would affect every gate while the run still
# records ordinary tool versions.
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source measurement refuses a BASH_ENV startup hook" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source measurement refuses inherited shell functions" >&2
    exit 2
fi

# Loader interposition can replace bcmp, allocation, or clock behavior in the
# exact binary whose hash is archived. GIT_DIR and its siblings would redirect
# the HEAD check below to a different repository than Cargo builds, and
# RIPGREP_CONFIG_PATH can drop files from the source manifests.
swept_environment_names=()
while IFS= read -r variable; do
    case $variable in
    LD_* | DYLD_* | GLIBC_TUNABLES | GIT_* | RIPGREP_CONFIG_PATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
if [[ -s /etc/ld.so.preload ]]; then
    echo "exact-source measurement refuses /etc/ld.so.preload interposition" >&2
    exit 2
fi
# Replacement objects would let the checked-out content differ from the commit.
export GIT_NO_REPLACE_OBJECTS=1

if [[ $# -ne 3 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256" >&2
    exit 2
fi

# Absolute: gate redirects and CARGO_TARGET_DIR are used after cd "$repo_root".
output_dir=$(realpath -m -- "$1")
source_commit=$2
source_archive_sha256=$3

# Ambient codegen flags would silently contradict the recorded generic/native
# flags; CARGO_ENCODED_RUSTFLAGS even overrides the native RUSTFLAGS below.
# An exported empty RUSTFLAGS suppresses CARGO_TARGET_<TRIPLE>_RUSTFLAGS,
# CARGO_BUILD_RUSTFLAGS, and cargo-config rustflags. Unsetting it does not.
ambient_rustflags=${RUSTFLAGS-<unset>}
ambient_encoded_rustflags=${CARGO_ENCODED_RUSTFLAGS-<unset>}
unset CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_TARGET
export RUSTFLAGS=''

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

# In-tree output would land in the source manifest, so before/after differ even
# though no source file changed.
case "$output_dir/" in
"$repo_root"/*)
    echo "output must live outside the repository: $output_dir" >&2
    exit 2
    ;;
esac

# The caller-supplied commit is otherwise unchecked evidence.
if git -C "$repo_root" rev-parse --git-dir >/dev/null 2>&1; then
    head_commit=$(git -C "$repo_root" rev-parse HEAD)
    if [[ $head_commit != "$source_commit" ]]; then
        echo "worktree HEAD $head_commit does not match SOURCE_COMMIT $source_commit" >&2
        exit 2
    fi
    if [[ -n $(git -C "$repo_root" status --porcelain) ]]; then
        echo "worktree is not clean; refusing exact-source evidence" >&2
        exit 2
    fi
    # assume-unchanged and skip-worktree entries keep a modified file out of the
    # status output while cargo still builds the working-tree bytes.
    marked_entries=$(git -C "$repo_root" ls-files -v |
        awk '$1 ~ /^[a-zS]$/ { count++ } END { print count + 0 }')
    if [[ $marked_entries -ne 0 ]]; then
        echo "worktree has $marked_entries assume-unchanged/skip-worktree entries" >&2
        exit 2
    fi
    source_commit_verified="git-worktree-head-clean"
else
    # ponytail: extracted archives keep the caller's word; recompute the archive
    # digest here if the promotion path ever stops hashing it.
    source_commit_verified="no-git-worktree-caller-supplied"
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
    echo "source_commit_verified=$source_commit_verified"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "repository_root=$repo_root"
    echo "host_runner=topics/034-string-matching-selection/experiment/run_host.sh"
} >"$output_dir/source_identity.txt"

# Captured before the write: echo returns 0 even when a substitution fails, so
# an inline substitution would archive an empty host identity.
resolved_hostname=$(hostname -f)
uname_all=$(uname -a)
host_architecture=$(uname -m)
host_kernel=$(uname -r)
host_cpu_count=$(nproc)
{
    echo "ssh_target=${SSH_TARGET_LABEL:-not-recorded-by-caller}"
    echo "resolved_hostname=$resolved_hostname"
    echo "uname_a=$uname_all"
    echo "architecture=$host_architecture"
    echo "kernel=$host_kernel"
    echo "available_cpu_count=$host_cpu_count"
    echo "shell=$BASH_VERSION"
    echo "generic_flags=baseline target; RUSTFLAGS exported empty"
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
# CARGO_* values can carry registry tokens (CARGO_REGISTRIES_*_TOKEN) and this
# file is promoted into the evidence archive, so record only their names.
{
    printf 'ambient_RUSTFLAGS=%s\n' "$ambient_rustflags"
    printf 'ambient_CARGO_ENCODED_RUSTFLAGS=%s\n' "$ambient_encoded_rustflags"
    printf 'generic_rustflags=empty-exported-RUSTFLAGS\n'
    printf 'swept=CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_TARGET\n'
    for variable_name in ${swept_environment_names[@]+"${swept_environment_names[@]}"}; do
        printf 'unset %s\n' "$variable_name"
    done
    compgen -e | LC_ALL=C sort | while IFS= read -r name; do
        case $name in
        CARGO | CARGO_*) printf 'name-only %s\n' "$name" ;;
        CC | CFLAGS | PATH | RUST*) printf '%s=%s\n' "$name" "${!name}" ;;
        esac
    done
} >"$output_dir/build_environment.txt"

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
# Relative paths keep sha256sum -c usable after the directory is archived.
(cd "$output_dir" && sha256sum ./*.asm) >"$output_dir/disassembly.sha256"

write_source_manifest "$output_dir/source_manifest.after.sha256"
cmp "$output_dir/source_manifest.before.sha256" "$output_dir/source_manifest.after.sha256"

# Written before the manifest so SHA256SUMS covers the pass record; the final
# stdout line below stays the run's success sentinel.
{
    echo "CHECK=PASS"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "benchmark_blocks=12"
    echo "aa_blocks=4"
    echo "timing_binary_sha256=$(sha256sum "$native_binary" | awk '{print $1}')"
} >"$output_dir/run.status"

manifest_temp="$work_dir/SHA256SUMS"
(
    cd "$output_dir"
    # No ignore filtering: an ancestor .ignore/.gitignore outside the checkout
    # could otherwise drop promoted evidence files from this manifest.
    rg --files --hidden --no-ignore -0 |
        LC_ALL=C sort -z |
        xargs -0 sha256sum
) >"$manifest_temp"
cp "$manifest_temp" "$output_dir/SHA256SUMS"

echo "CHECK=PASS output=$output_dir"
