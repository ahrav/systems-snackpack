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
    RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTDOC | \
        CARGO_BUILD_* | CARGO_TARGET_* | CARGO_PROFILE_* | CARGO_UNSTABLE_* | \
        CARGO_INCREMENTAL | MALLOC_* | \
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

# A PATH edit made before this script started cannot be detected from inside it.
# The provenance record identifies the resolved tool binaries.
record_tool_provenance() {
    local destination=$1 tool tool_path tool_digest
    {
        for tool in bash cargo rustc python3 git rg nm objdump sha256sum awk cmp comm realpath \
            hostname uname lscpu nproc taskset paste sort xargs cat env tar find gzip diff head ldd ln \
            cp mkdir cc ld; do
            if ! tool_path=$(type -P "$tool"); then
                echo "required tool is absent from PATH: $tool" >&2
                exit 2
            fi
            tool_digest=$(sha256sum "$(realpath "$tool_path")" | awk '{print $1}')
            printf '%s path=%s sha256=%s\n' "$tool" "$tool_path" "$tool_digest"
        done
    } >"$destination"
}

# Captured before the archive digest and the source identity checks, which are
# themselves produced by recorded tools.
tool_provenance_baseline=$(record_tool_provenance /dev/stdout)

if [[ $# -lt 3 || $# -gt 4 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [SOURCE_ARCHIVE]" >&2
    exit 2
fi

# Absolute: gate redirects and CARGO_TARGET_DIR are used after cd "$repo_root".
output_dir=$(realpath -m -- "$1")
source_commit=$2
source_archive_sha256=$3

# The digest names bytes this script never sees unless the archive is passed too.
if [[ $# -eq 4 ]]; then
    source_archive=$(realpath -m -- "$4")
    archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
    if [[ $archive_digest != "$source_archive_sha256" ]]; then
        echo "archive $source_archive hashes to $archive_digest, not $source_archive_sha256" >&2
        exit 2
    fi
    source_archive_verified="digest-and-tree-compared"
else
    source_archive=""
    source_archive_verified="no-archive-supplied-caller-metadata"
fi

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

script_source=$0
if [[ $script_source != */* ]]; then
    if ! script_source=$(type -P "$script_source"); then
        echo "cannot locate this script from $0" >&2
        exit 2
    fi
fi
script_dir=$(cd -- "${script_source%/*}" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
work_dir="${output_dir}.work"
build_root="$work_dir/source-snapshot"
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

# Cargo reads config files from the working directory upward, and settings such
# as build.rustc-wrapper or a linker survive the empty RUSTFLAGS above.
config_search_dir=$repo_root
while :; do
    for cargo_config in "$config_search_dir/.cargo/config.toml" "$config_search_dir/.cargo/config"; do
        if [[ -e $cargo_config ]]; then
            echo "refusing ambient cargo config: $cargo_config" >&2
            exit 2
        fi
    done
    if [[ $config_search_dir == / ]]; then
        break
    fi
    config_search_dir=${config_search_dir%/*}
    config_search_dir=${config_search_dir:-/}
done

# The caller-supplied commit is otherwise unchecked evidence.
verify_worktree_identity() {
    # A configured core.fsmonitor hook can report a modified file as unchanged.
    local git_verify=(git -c core.fsmonitor=false -c core.untrackedCache=false -C "$repo_root")
    if ! "${git_verify[@]}" rev-parse --git-dir >/dev/null 2>&1; then
        # An extracted archive carries no git metadata, so the caller-supplied
        # commit is recorded as unverified.
        source_commit_verified="no-git-worktree-caller-supplied"
        return 0
    fi
    local head_commit marked_entries
    head_commit=$("${git_verify[@]}" rev-parse HEAD)
    if [[ $head_commit != "$source_commit" ]]; then
        echo "worktree HEAD $head_commit does not match SOURCE_COMMIT $source_commit" >&2
        exit 2
    fi
    if [[ -n $("${git_verify[@]}" status --porcelain) ]]; then
        echo "worktree is not clean; refusing exact-source evidence" >&2
        exit 2
    fi
    # assume-unchanged and skip-worktree entries keep a modified file out of the
    # status output while cargo still builds the working-tree bytes.
    marked_entries=$("${git_verify[@]}" ls-files -v |
        awk '$1 ~ /^[a-zS]$/ { count++ } END { print count + 0 }')
    if [[ $marked_entries -ne 0 ]]; then
        echo "worktree has $marked_entries assume-unchanged/skip-worktree entries" >&2
        exit 2
    fi
    # Ignored files stay out of both git status and the ignore-aware manifest, yet
    # cargo still consumes them: an ignored build.rs runs during the build.
    local extra_files
    extra_files=$(comm -13 \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD | LC_ALL=C sort) \
        <(cd "$repo_root" && rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' |
            LC_ALL=C sort))
    if [[ -n $extra_files ]]; then
        echo "working tree has files absent from $source_commit:" >&2
        printf '%s\n' "$extra_files" >&2
        exit 2
    fi
    # The verifier rehashes working bytes against commit blobs because git's stat
    # cache can report a modified file as clean.
    local recorded_blobs rehashed_blobs
    recorded_blobs=$("${git_verify[@]}" ls-tree -r HEAD |
        awk -F'\t' '{ split($1, fields, " "); print fields[3] " " $2 }' | LC_ALL=C sort)
    rehashed_blobs=$(cd "$repo_root" && paste -d' ' \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD |
            git -C "$repo_root" hash-object --no-filters --stdin-paths) \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD) | LC_ALL=C sort)
    if [[ $recorded_blobs != "$rehashed_blobs" ]]; then
        echo "working tree content differs from $source_commit:" >&2
        comm -13 <(printf '%s\n' "$recorded_blobs") <(printf '%s\n' "$rehashed_blobs") >&2
        exit 2
    fi
    source_commit_verified="git-worktree-head-rehashed"
}

verify_worktree_identity

mkdir -p "$output_dir" "$work_dir"
generic_target="$work_dir/generic-target"
native_target="$work_dir/native-target"

write_source_manifest() {
    local destination=$1
    local root=${2:-$repo_root}
    local symlinked_inputs
    # rg does not follow symlinks, so a symlinked input would be hashed nowhere.
    # Cargo still compiles the symlink target.
    symlinked_inputs=$(find "$root" \( -path "$root/target" -o -path "$root/.git" \) -prune -o \
        -type l -print | LC_ALL=C sort)
    if [[ -n $symlinked_inputs ]]; then
        echo "refusing symlinked source inputs under $root:" >&2
        printf '%s\n' "$symlinked_inputs" >&2
        exit 2
    fi
    (
        cd "$root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z |
            xargs -0 sha256sum
    ) >"$destination"
}

# Hashing the archive says nothing about the tree cargo builds, so its contents
# are compared with the pre-build manifest.
verify_source_archive() {
    local archive=$1 extract_dir="$work_dir/archive-source" runner_suffix archive_root marker
    runner_suffix="topics/034-string-matching-selection/experiment/run_host.sh"
    mkdir -p "$extract_dir"
    tar -xzf "$archive" -C "$extract_dir"
    marker=$(cd "$extract_dir" && find . -type f -path "*/$runner_suffix" | LC_ALL=C sort | head -1)
    if [[ -z $marker ]]; then
        echo "archive $archive does not contain $runner_suffix" >&2
        exit 2
    fi
    archive_root=$(cd "$extract_dir" && cd "${marker%/"$runner_suffix"}" && pwd -P)
    write_source_manifest "$work_dir/archive_manifest.sha256" "$archive_root"
    if ! cmp -s "$output_dir/source_manifest.before.sha256" "$work_dir/archive_manifest.sha256"; then
        echo "archive $archive does not match the source tree at $repo_root:" >&2
        diff "$output_dir/source_manifest.before.sha256" "$work_dir/archive_manifest.sha256" >&2 || true
        exit 2
    fi
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
    echo "source_archive_verified=$source_archive_verified"
    echo "repository_root=$repo_root"
    echo "build_root=$build_root"
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
    echo "pid_max=$(cat /proc/sys/kernel/pid_max 2>/dev/null || echo not-readable)"
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

# Cargo also reads $CARGO_HOME/config.toml, which legitimately carries registry
# mirrors, so its digest is recorded instead of refused.
# A relative CARGO_HOME would resolve against a different directory once cargo
# runs after the cd below.
# The isolated CARGO_HOME bypasses config.toml and config in the original
# CARGO_HOME; the registry cache is reused by symlink.
real_cargo_home=$(realpath -m -- "${CARGO_HOME:-$HOME/.cargo}")
cargo_home="$work_dir/cargo-home"
mkdir -p "$cargo_home"
for cache_entry in registry git; do
    if [[ -e "$real_cargo_home/$cache_entry" ]]; then
        ln -s "$real_cargo_home/$cache_entry" "$cargo_home/$cache_entry"
    fi
done
export CARGO_HOME=$cargo_home
{
    printf 'cargo_home=%s\n' "$cargo_home"
    printf 'cargo_home_isolated_from=%s\n' "$real_cargo_home"
    for cargo_config in "$real_cargo_home/config.toml" "$real_cargo_home/config"; do
        if [[ -e $cargo_config ]]; then
            config_digest=$(sha256sum "$cargo_config" | awk '{print $1}')
            printf 'bypassed_cargo_home_config=%s sha256=%s\n' "$cargo_config" "$config_digest"
        fi
    done
} >>"$output_dir/build_environment.txt"

printf '%s\n' "$tool_provenance_baseline" >"$output_dir/tool_provenance.txt"

# rustup which records the selected tool binary when rustup manages it, and the
# sysroot holds the linker and precompiled standard library used by the build.
record_toolchain_provenance() {
    local destination=$1 rust_sysroot proxied selected selected_digest artifact artifact_digest
    rust_sysroot=$(rustc --print sysroot)
    {
        printf 'sysroot=%s\n' "$rust_sysroot"
        for proxied in cargo rustc rustdoc; do
            if selected=$(rustup which "$proxied" 2>/dev/null); then
                selected_digest=$(sha256sum "$selected" | awk '{print $1}')
                printf '%s selected=%s sha256=%s\n' "$proxied" "$selected" "$selected_digest"
            else
                printf '%s selected=no-rustup-proxy\n' "$proxied"
            fi
        done
        while IFS= read -r artifact; do
            artifact_digest=$(sha256sum "$artifact" | awk '{print $1}')
            printf '%s sha256=%s\n' "$artifact" "$artifact_digest"
        done < <(find "$rust_sysroot/lib" -type f \
            \( -name '*.rlib' -o -name '*.so' -o -name 'rust-lld' -o -name 'ld.lld' \) |
            LC_ALL=C sort)
    } >"$destination"
}
record_toolchain_provenance "$output_dir/toolchain_provenance.txt"

write_source_manifest "$output_dir/source_manifest.before.sha256"
if [[ -n $source_archive ]]; then
    verify_source_archive "$source_archive"
fi

# Builds run from a snapshot, so a source change during them cannot reach the
# compiler and vanish before the after-manifest.
mkdir -p "$build_root"
tar -C "$repo_root" --exclude=./target --exclude=./.git -cf - . |
    tar -C "$build_root" -xf -
write_source_manifest "$work_dir/snapshot_manifest.sha256" "$build_root"
cmp "$output_dir/source_manifest.before.sha256" "$work_dir/snapshot_manifest.sha256"
# verify_worktree_identity runs again after the manifest: a modification landing
# between the first check and this manifest would appear in both manifests and
# pass the cmp gate below.
verify_worktree_identity

cd "$build_root"

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
native_digest_before_timing=$(sha256sum "$native_binary" | awk '{print $1}')
sha256sum "$native_binary" >"$output_dir/native_binary.sha256"

# The binary digest excludes shared libraries resolved at run time.
record_runtime_libraries() {
    local listing=$1 digests=$2 library_path library_digest
    ldd "$native_binary" >"$listing" 2>&1
    : >"$digests"
    while IFS= read -r library_path; do
        library_digest=$(sha256sum "$library_path" | awk '{print $1}')
        printf '%s sha256=%s\n' "$library_path" "$library_digest" >>"$digests"
    done < <(awk '$0 ~ /=> \// { print $3 } $1 ~ /^\// { print $1 }' "$listing" |
        LC_ALL=C sort -u)
}
record_runtime_libraries "$output_dir/native_libraries.txt" \
    "$output_dir/native_libraries.sha256"

python3 -I topics/034-string-matching-selection/experiment/run_processes.py \
    --binary "$native_binary" \
    --output "$output_dir/benchmark" \
    --blocks 12 \
    --aa-blocks 4 \
    --seed 340034 \
    --target-ms 200 >"$output_dir/benchmark_runner.log" 2>&1

python3 -I topics/034-string-matching-selection/experiment/validate_receipts.py \
    --expect-binary-sha256 "$native_digest_before_timing" \
    --expect-attempts-root "$output_dir/benchmark/" \
    "$output_dir/benchmark" >"$output_dir/receipt_validation.log" 2>&1

# One executable must serve the whole timing run for the contrasts to compare
# the same bytes.
native_digest_after_timing=$(sha256sum "$native_binary" | awk '{print $1}')
if [[ $native_digest_after_timing != "$native_digest_before_timing" ]]; then
    echo "native binary changed during the timing run" >&2
    exit 2
fi

# A toolchain replacement mid-run would leave the builds on other bytes.
record_toolchain_provenance "$work_dir/toolchain_provenance.after.txt"
if ! cmp -s "$output_dir/toolchain_provenance.txt" "$work_dir/toolchain_provenance.after.txt"; then
    echo "toolchain changed during the run:" >&2
    diff "$output_dir/toolchain_provenance.txt" "$work_dir/toolchain_provenance.after.txt" >&2 || true
    exit 2
fi

# A library upgrade during the run would leave later processes on other bytes.
record_runtime_libraries "$work_dir/native_libraries.after.txt" \
    "$work_dir/native_libraries.after.sha256"
if ! cmp -s "$output_dir/native_libraries.sha256" "$work_dir/native_libraries.after.sha256"; then
    echo "runtime libraries changed during the timing run:" >&2
    diff "$output_dir/native_libraries.sha256" "$work_dir/native_libraries.after.sha256" >&2 || true
    exit 2
fi

nm -n "$native_binary" |
    rg 'topic034_(left_to_right|kmp|horspool)_find|(KmpPlan|HorspoolPlan)3new' >"$output_dir/symbols.txt"
for symbol in \
    topic034_left_to_right_find \
    topic034_kmp_find \
    topic034_horspool_find
do
    objdump -d --no-show-raw-insn --disassemble="$symbol" "$native_binary" \
        >"$output_dir/${symbol}.asm"
    rg -q "<$symbol>" "$output_dir/${symbol}.asm"
done
plan_symbol_count=0
while IFS= read -r plan_symbol; do
    objdump -d --no-show-raw-insn --disassemble="$plan_symbol" "$native_binary" \
        >"$output_dir/${plan_symbol}.asm"
    rg -q "<$plan_symbol>" "$output_dir/${plan_symbol}.asm"
    plan_symbol_count=$((plan_symbol_count + 1))
done < <(nm "$native_binary" |
    awk '$3 ~ /(KmpPlan|HorspoolPlan)3new/ { print $3 }' | LC_ALL=C sort -u)
printf 'out_of_line_plan_constructors=%s\n' "$plan_symbol_count" >>"$output_dir/symbols.txt"
# Relative paths keep sha256sum -c usable after the directory is archived.
(cd "$output_dir" && sha256sum ./*.asm) >"$output_dir/disassembly.sha256"

# The disassembly must describe the binary the timings came from.
native_digest_after_disassembly=$(sha256sum "$native_binary" | awk '{print $1}')
if [[ $native_digest_after_disassembly != "$native_digest_before_timing" ]]; then
    echo "native binary changed during linked-code inspection" >&2
    exit 2
fi

write_source_manifest "$output_dir/source_manifest.after.sha256" "$build_root"
cmp "$output_dir/source_manifest.before.sha256" "$output_dir/source_manifest.after.sha256"

native_timing_digest=$(sha256sum "$native_binary" | awk '{print $1}')
if [[ $native_timing_digest != "$native_digest_before_timing" ]]; then
    echo "native binary changed before the pass record was written" >&2
    exit 2
fi

# Written before the manifest so SHA256SUMS covers the pass record; the final
# stdout line below stays the run's success sentinel.
{
    echo "CHECK=PASS"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "benchmark_blocks=12"
    echo "aa_blocks=4"
    echo "timing_binary_sha256=$native_timing_digest"
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

# Checked last, after every recorded tool has produced its final output.
record_tool_provenance "$work_dir/tool_provenance.after.txt"
if ! cmp -s "$output_dir/tool_provenance.txt" "$work_dir/tool_provenance.after.txt"; then
    echo "CHECK=FAIL tool_provenance_changed" >"$output_dir/run.status"
    echo "a recorded tool changed during the run:" >&2
    diff "$output_dir/tool_provenance.txt" "$work_dir/tool_provenance.after.txt" >&2 || true
    exit 2
fi

echo "CHECK=PASS output=$output_dir"
