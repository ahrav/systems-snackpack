#!/usr/bin/env bash
set -euo pipefail

# This runner is intentionally GNU/Linux-specific. It uses task affinity,
# /proc and cgroup evidence, ELF dynamic-library inspection, and GNU objdump.
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source measurement refuses BASH_ENV" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source measurement refuses inherited shell functions" >&2
    exit 2
fi

swept_environment_names=()
while IFS= read -r variable; do
    case $variable in
    RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTDOC | RUSTFMT | \
        RUSTFLAGS | RUSTDOCFLAGS | CARGO_ENCODED_RUSTFLAGS | CARGO_INCREMENTAL | \
        CARGO_BUILD_* | CARGO_TARGET_* | CARGO_PROFILE_* | CARGO_UNSTABLE_* | \
        CC | CFLAGS | CPPFLAGS | LDFLAGS | COMPILER_PATH | GCC_EXEC_PREFIX | \
        LIBRARY_PATH | CPATH | C_INCLUDE_PATH | CPLUS_INCLUDE_PATH | \
        LD_* | DYLD_* | GLIBC_TUNABLES | MALLOC_* | GIT_* | \
        RIPGREP_CONFIG_PATH | CDPATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
if [[ -s /etc/ld.so.preload ]]; then
    echo "exact-source measurement refuses /etc/ld.so.preload" >&2
    exit 2
fi
export GIT_NO_REPLACE_OBJECTS=1
export RUSTFLAGS=''

if [[ $# -ne 4 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 SOURCE_ARCHIVE" >&2
    exit 2
fi
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to xxl or the authorized Arm hostname}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the resolved backing hostname}"

output_dir=$(realpath -m -- "$1")
source_commit=${2,,}
source_archive_sha256=${3,,}
if [[ ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
    echo "SOURCE_ARCHIVE_SHA256 must be 64 hexadecimal digits" >&2
    exit 2
fi
if [[ ! $source_commit =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]; then
    echo "SOURCE_COMMIT must be a full 40- or 64-hex-digit object ID" >&2
    exit 2
fi
if [[ -e $output_dir ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi

source_archive=$(realpath -m -- "$4")
archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $archive_digest != "$source_archive_sha256" ]]; then
    echo "source archive digest mismatch" >&2
    exit 2
fi
source_archive_verified=digest-verified-tree-gate-pending

script_source=$0
if [[ $script_source != */* ]]; then
    script_source=$(type -P "$script_source")
fi
script_dir=$(cd -- "${script_source%/*}" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
work_dir="${output_dir}.work"
build_root="$work_dir/source-snapshot"
if [[ -e $work_dir ]]; then
    echo "work directory already exists: $work_dir" >&2
    exit 2
fi
case "$output_dir/" in
"$repo_root"/*)
    echo "output must live outside the repository" >&2
    exit 2
    ;;
esac

resolved_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $resolved_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    echo "resolved host mismatch: expected $SSH_RESOLVED_HOSTNAME, got $resolved_hostname" >&2
    exit 1
fi
case "$SSH_TARGET_LABEL" in
xxl)
    [[ $architecture == x86_64 ]] || {
        echo "xxl must resolve to x86_64; got $architecture" >&2
        exit 1
    }
    ;;
dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
    [[ $architecture == aarch64 || $architecture == arm64 ]] || {
        echo "authorized Arm host must be aarch64/arm64; got $architecture" >&2
        exit 1
    }
    ;;
*)
    echo "unexpected SSH target label: $SSH_TARGET_LABEL" >&2
    exit 2
    ;;
esac

refuse_ambient_cargo_config() {
    local search_dir=$1 cargo_config
    while :; do
        for cargo_config in "$search_dir/.cargo/config.toml" "$search_dir/.cargo/config"; do
            if [[ -e $cargo_config ]]; then
                echo "refusing ambient cargo config: $cargo_config" >&2
                exit 2
            fi
        done
        [[ $search_dir == / ]] && break
        search_dir=${search_dir%/*}
        search_dir=${search_dir:-/}
    done
}
refuse_ambient_cargo_config "$repo_root"

git_verify=(git -c core.fsmonitor=false -c core.untrackedCache=false -C "$repo_root")
if [[ $("${git_verify[@]}" rev-parse --show-toplevel 2>/dev/null || true) == "$repo_root" ]]; then
    head_commit=$("${git_verify[@]}" rev-parse HEAD)
    expected_commit=$("${git_verify[@]}" rev-parse --verify "${source_commit}^{commit}")
    resolved_source_commit=$expected_commit
    if [[ $source_commit != "$resolved_source_commit" ]]; then
        echo "supplied full commit $source_commit resolved unexpectedly to $resolved_source_commit" >&2
        exit 2
    fi
    if [[ $head_commit != "$resolved_source_commit" ]]; then
        echo "HEAD $head_commit does not match source commit $expected_commit" >&2
        exit 2
    fi
    if [[ -n $("${git_verify[@]}" status --porcelain) ]]; then
        echo "worktree is not clean" >&2
        exit 2
    fi
    marked_entries=$("${git_verify[@]}" ls-files -v |
        awk '$1 ~ /^[a-zS]$/ { count++ } END { print count + 0 }')
    if [[ $marked_entries -ne 0 ]]; then
        echo "worktree has assume-unchanged or skip-worktree entries" >&2
        exit 2
    fi
    extra_files=$(comm -13 \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD | LC_ALL=C sort) \
        <(cd "$repo_root" && rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' |
            LC_ALL=C sort))
    if [[ -n $extra_files ]]; then
        echo "worktree contains files absent from the source commit:" >&2
        printf '%s\n' "$extra_files" >&2
        exit 2
    fi
    recorded_blobs=$("${git_verify[@]}" ls-tree -r HEAD |
        awk -F'\t' '{ split($1, fields, " "); print fields[3] " " $2 }' | LC_ALL=C sort)
    rehashed_blobs=$(cd "$repo_root" && paste -d' ' \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD |
            git -C "$repo_root" hash-object --no-filters --stdin-paths) \
        <("${git_verify[@]}" ls-tree -r --name-only HEAD) | LC_ALL=C sort)
    if [[ $recorded_blobs != "$rehashed_blobs" ]]; then
        echo "worktree bytes differ from commit blobs" >&2
        exit 2
    fi
    source_commit_verified=git-worktree-head-rehashed
else
    resolved_source_commit=$source_commit
    source_commit_verified=no-git-worktree-archive-tree-and-digest
fi

mkdir -p "$output_dir" "$work_dir" "$build_root"
generic_target="$work_dir/generic-rust-target"
native_target="$work_dir/native-rust-target"
generic_c_binary="$work_dir/compression-probe-generic"
native_c_binary="$work_dir/compression-probe-native"

write_source_manifest() {
    local destination=$1 root=${2:-$repo_root} symlinks
    symlinks=$(find "$root" \( -path "$root/target" -o -path "$root/.git" \) -prune -o \
        -type l -print | LC_ALL=C sort)
    if [[ -n $symlinks ]]; then
        echo "refusing symlinked source inputs" >&2
        printf '%s\n' "$symlinks" >&2
        exit 2
    fi
    (
        cd "$root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum
    ) >"$destination"
}

verify_source_archive() {
    local archive=$1 extract_dir="$work_dir/archive-source" marker archive_root
    local runner_suffix=topics/037-compression-systems-primitive/experiment/run_host.sh
    mkdir -p "$extract_dir"
    tar -xzf "$archive" -C "$extract_dir"
    marker=$(cd "$extract_dir" && find . -type f -path "*/$runner_suffix" | LC_ALL=C sort | head -1)
    [[ -n $marker ]] || {
        echo "archive does not contain Topic 37 host runner" >&2
        exit 2
    }
    archive_root=$(cd "$extract_dir" && cd "${marker%/"$runner_suffix"}" && pwd -P)
    write_source_manifest "$work_dir/archive_manifest.sha256" "$archive_root"
    cmp "$output_dir/source_manifest.before.sha256" "$work_dir/archive_manifest.sha256"
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

record_tools() {
    local destination=$1 tool path digest
    : >"$destination"
    for tool in bash cargo rustc python3 git rg nm objdump sha256sum awk cmp comm realpath \
        hostname uname lscpu nproc taskset sort xargs env tar find diff head ldd ldconfig \
        cc ld rustfmt cargo-fmt cargo-clippy clippy-driver chmod sed cat cp ln mkdir paste tr; do
        path=$(type -P "$tool") || {
            echo "required tool missing: $tool" >&2
            exit 2
        }
        digest=$(sha256sum "$(realpath "$path")" | awk '{print $1}')
        printf '%s path=%s sha256=%s\n' "$tool" "$path" "$digest" >>"$destination"
    done
}

record_runtime_libraries() {
    local listing=$1 digests=$2 library_path
    ldd "$native_c_binary" >"$listing" 2>&1
    : >"$digests"
    while IFS= read -r library_path; do
        library_path=$(realpath "$library_path")
        printf '%s sha256=%s\n' "$library_path" "$(sha256sum "$library_path" | awk '{print $1}')" \
            >>"$digests"
    done < <(awk '$0 ~ /=> \/+/ { print $3 } $1 ~ /^\// { print $1 }' "$listing" |
        LC_ALL=C sort -u)
}

record_tools "$output_dir/tool_provenance.before.txt"
{
    echo "ssh_alias=$SSH_TARGET_LABEL"
    echo "configured_hostname=$SSH_RESOLVED_HOSTNAME"
    echo "resolved_remote_hostname=$resolved_hostname"
    echo "uname_m=$architecture"
    echo "uname_a=$(uname -a)"
    echo "kernel=$(uname -r)"
    echo "available_cpu_count=$(nproc)"
    echo "configured_cpu_count=$(nproc --all)"
    echo "linux_gnu_boundary=required"
    echo "identity_boundary=memcpy-control-not-zero-copy"
    echo "generic_c_flags=-O3 -fno-omit-frame-pointer -std=gnu11 -Wall -Wextra -Wpedantic -Werror"
    echo "native_c_flags=generic plus -march=native -g"
} >"$output_dir/host.txt"

lscpu >"$output_dir/lscpu.txt" 2>&1
record_optional cpuinfo.txt sed -n 1,500p /proc/cpuinfo
record_optional process_status.txt cat /proc/self/status
record_optional process_cgroup.txt cat /proc/self/cgroup
record_optional cgroup_cpu_max.txt cat /sys/fs/cgroup/cpu.max
record_optional cgroup_cpuset_effective.txt cat /sys/fs/cgroup/cpuset.cpus.effective
record_optional cgroup_cpu_pressure.txt cat /sys/fs/cgroup/cpu.pressure
taskset -pc $$ >"$output_dir/affinity.txt" 2>&1
rustc -Vv >"$output_dir/rustc.txt" 2>&1
cargo -V >"$output_dir/cargo.txt" 2>&1
python3 --version >"$output_dir/python.txt" 2>&1
python3 -c 'import sys; assert sys.version_info >= (3, 9)' \
    >>"$output_dir/python.txt" 2>&1
cc --version >"$output_dir/cc.txt" 2>&1
rustc --print target-features >"$output_dir/rust_target_features.txt" 2>&1
cc -Q -O3 -march=native --help=target >"$output_dir/cc_native_target.txt" 2>&1 || true
{
    printf 'swept=%s\n' "${swept_environment_names[*]-}"
    printf 'RUSTFLAGS=empty-exported\n'
    printf 'LC_ALL=C for timed children\n'
    printf 'TZ=UTC for timed children\n'
} >"$output_dir/build_environment.txt"

real_cargo_home=$(realpath -m -- "${CARGO_HOME:-$HOME/.cargo}")
cargo_home="$work_dir/cargo-home"
mkdir -p "$cargo_home"
for cache_entry in registry git; do
    [[ ! -e "$real_cargo_home/$cache_entry" ]] || ln -s "$real_cargo_home/$cache_entry" "$cargo_home/$cache_entry"
done
export CARGO_HOME=$cargo_home

write_source_manifest "$output_dir/source_manifest.before.sha256"
verify_source_archive "$source_archive"
source_archive_verified=digest-and-tree-compared
{
    echo "source_commit_supplied=$source_commit"
    echo "source_commit_resolved=$resolved_source_commit"
    echo "source_commit_verified=$source_commit_verified"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "source_archive_verified=$source_archive_verified"
    echo "repository_root=$repo_root"
    echo "build_root=$build_root"
    echo "host_runner=topics/037-compression-systems-primitive/experiment/run_host.sh"
} >"$output_dir/source_identity.txt"
tar -C "$repo_root" --exclude=./target --exclude=./.git -cf - . | tar -C "$build_root" -xf -
write_source_manifest "$work_dir/snapshot_manifest.sha256" "$build_root"
cmp "$output_dir/source_manifest.before.sha256" "$work_dir/snapshot_manifest.sha256"
find "$build_root" -type f -exec chmod a-w {} +
refuse_ambient_cargo_config "$build_root"

cd "$build_root"
export CARGO_TARGET_DIR=$generic_target
run_gate fmt.log cargo fmt --all -- --check
run_gate test_lib_examples.log cargo test --locked --workspace --lib --examples
run_gate test_doc.log cargo test --locked --workspace --doc
run_gate clippy.log cargo clippy --locked --workspace --all-targets -- -D warnings
run_gate bench_build.log cargo bench --locked --workspace --no-run
export RUSTDOCFLAGS='-D warnings'
run_gate doc_build.log cargo doc --locked --workspace --no-deps
unset RUSTDOCFLAGS
run_gate rust_generic_build.log cargo build --locked --release \
    --package compression-systems-primitive --bin compression-contract-probe
rust_generic="$generic_target/release/compression-contract-probe"
run_gate rust_generic_verify.log "$rust_generic" verify

export CARGO_TARGET_DIR=$native_target
export RUSTFLAGS='-C target-cpu=native -C debuginfo=1'
run_gate rust_native_build.log cargo build --locked --release \
    --package compression-systems-primitive --bin compression-contract-probe
export RUSTFLAGS=''
unset CARGO_TARGET_DIR
rust_native="$native_target/release/compression-contract-probe"
run_gate rust_native_verify.log "$rust_native" verify
sha256sum "$rust_generic" "$rust_native" >"$output_dir/rust_binaries.sha256"

probe_source=topics/037-compression-systems-primitive/experiment/compression_probe.c
runner_source=topics/037-compression-systems-primitive/experiment/run_processes.py
validator_source=topics/037-compression-systems-primitive/experiment/validate_receipts.py
lz4_library=$(ldconfig -p | awk '$1 ~ /^liblz4\.so\.1$/ { print $NF; exit }')
zstd_library=$(ldconfig -p | awk '$1 ~ /^libzstd\.so\.1$/ { print $NF; exit }')
if [[ -z $lz4_library || -z $zstd_library ]]; then
    echo "versioned LZ4 or zstd runtime library was not found" >&2
    exit 2
fi
lz4_library=$(realpath "$lz4_library")
zstd_library=$(realpath "$zstd_library")
sha256sum "$probe_source" "$runner_source" "$validator_source" \
    "$lz4_library" "$zstd_library" >"$output_dir/native_inputs.before.sha256"
cc -M "$probe_source" >"$output_dir/c_header_dependencies.before.txt"
tr ' \\' '\n' <"$output_dir/c_header_dependencies.before.txt" |
    rg '^/' | LC_ALL=C sort -u | xargs sha256sum >"$output_dir/c_headers.before.sha256"

generic_c_flags=(-O3 -fno-omit-frame-pointer -std=gnu11 -Wall -Wextra -Wpedantic -Werror)
native_c_flags=("${generic_c_flags[@]}" -march=native -g)
run_gate c_generic_build.log cc "${generic_c_flags[@]}" "$probe_source" \
    -o "$generic_c_binary" "$zstd_library" "$lz4_library"
run_gate c_generic_verify.log "$generic_c_binary" verify
run_gate c_native_build.log cc "${native_c_flags[@]}" "$probe_source" \
    -o "$native_c_binary" "$zstd_library" "$lz4_library"
run_gate c_native_verify.log "$native_c_binary" verify
native_digest_before=$(sha256sum "$native_c_binary" | awk '{print $1}')
sha256sum "$generic_c_binary" "$native_c_binary" >"$output_dir/c_binaries.sha256"
record_runtime_libraries "$output_dir/native_libraries.before.txt" \
    "$output_dir/native_libraries.before.sha256"

python3 -I "$runner_source" \
    --binary "$native_c_binary" \
    --source "$build_root/$probe_source" \
    --validator "$build_root/$validator_source" \
    --output "$output_dir/benchmark" \
    --blocks 12 --aa-blocks 4 --startup-per-phase 12 --seed 370037 --target-ms 200 \
    >"$output_dir/benchmark_runner.log" 2>&1
python3 -I "$validator_source" "$output_dir/benchmark" --binary "$native_c_binary" \
    >"$output_dir/receipt_validation.log" 2>&1

hash_benchmark_tree() {
    local destination=$1 symlinks
    symlinks=$(find "$output_dir/benchmark" -type l -print | LC_ALL=C sort)
    [[ -z $symlinks ]] || {
        echo "benchmark evidence contains symlinks" >&2
        exit 2
    }
    (
        cd "$output_dir/benchmark"
        rg --files --hidden --no-ignore -0 | LC_ALL=C sort -z | xargs -0 sha256sum
    ) >"$destination"
}
hash_benchmark_tree "$work_dir/benchmark.validated.sha256"

[[ $(sha256sum "$native_c_binary" | awk '{print $1}') == "$native_digest_before" ]] || {
    echo "native timing binary changed" >&2
    exit 2
}
sha256sum "$probe_source" "$runner_source" "$validator_source" \
    "$lz4_library" "$zstd_library" >"$output_dir/native_inputs.after.sha256"
cmp "$output_dir/native_inputs.before.sha256" "$output_dir/native_inputs.after.sha256"
cc -M "$probe_source" >"$output_dir/c_header_dependencies.after.txt"
tr ' \\' '\n' <"$output_dir/c_header_dependencies.after.txt" |
    rg '^/' | LC_ALL=C sort -u | xargs sha256sum >"$output_dir/c_headers.after.sha256"
cmp "$output_dir/c_header_dependencies.before.txt" "$output_dir/c_header_dependencies.after.txt"
cmp "$output_dir/c_headers.before.sha256" "$output_dir/c_headers.after.sha256"
sha256sum "$native_c_binary" >"$output_dir/native_binary.after.sha256"
record_runtime_libraries "$output_dir/native_libraries.after.txt" \
    "$output_dir/native_libraries.after.sha256"
cmp "$output_dir/native_libraries.before.sha256" "$output_dir/native_libraries.after.sha256"

nm -n "$native_c_binary" |
    rg 'topic037_(encode|decode)_all| (LZ4_|ZSTD_)' >"$output_dir/symbols.txt"
for symbol in topic037_encode_all topic037_decode_all; do
    [[ $(rg -c " $symbol$" "$output_dir/symbols.txt" || true) -eq 1 ]] || {
        echo "expected one linked $symbol" >&2
        exit 1
    }
    objdump -d --no-show-raw-insn --disassemble="$symbol" "$native_c_binary" \
        >"$output_dir/${symbol}.asm"
    rg -q "<$symbol>" "$output_dir/${symbol}.asm"
done
objdump -T "$native_c_binary" |
    rg 'LZ4_(compress_default|decompress_safe)|ZSTD_(compressCCtx|decompressDCtx|findFrameCompressedSize)' \
    >"$output_dir/dynamic_codec_imports.txt"
for codec_symbol in LZ4_compress_default LZ4_decompress_safe ZSTD_compressCCtx \
    ZSTD_decompressDCtx ZSTD_findFrameCompressedSize; do
    [[ $(awk -v symbol="$codec_symbol" '$NF == symbol { count++ } END { print count + 0 }' \
        "$output_dir/dynamic_codec_imports.txt") -eq 1 ]] || {
        echo "expected exactly one dynamic import for $codec_symbol" >&2
        exit 1
    }
done
(cd "$output_dir" && sha256sum ./topic037_*.asm) >"$output_dir/disassembly.sha256"
[[ $(sha256sum "$native_c_binary" | awk '{print $1}') == "$native_digest_before" ]] || {
    echo "native timing binary changed during inspection" >&2
    exit 2
}

write_source_manifest "$output_dir/source_manifest.after.sha256" "$build_root"
cmp "$output_dir/source_manifest.before.sha256" "$output_dir/source_manifest.after.sha256"
hash_benchmark_tree "$work_dir/benchmark.final.sha256"
cmp "$work_dir/benchmark.validated.sha256" "$work_dir/benchmark.final.sha256"
record_tools "$output_dir/tool_provenance.after.txt"
cmp "$output_dir/tool_provenance.before.txt" "$output_dir/tool_provenance.after.txt"

{
    echo "CHECK=PASS"
    echo "source_commit_supplied=$source_commit"
    echo "source_commit_resolved=$resolved_source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
    echo "ssh_target_label=$SSH_TARGET_LABEL"
    echo "ssh_resolved_backing_hostname=$SSH_RESOLVED_HOSTNAME"
    echo "architecture=$architecture"
    echo "benchmark_blocks=12"
    echo "aa_blocks=4"
    echo "timed_processes=176"
    echo "startup_processes=24"
    echo "timing_binary_sha256=$native_digest_before"
    echo "receipt_validation=$(tr '\n' ' ' <"$output_dir/receipt_validation.log")"
} >"$output_dir/run.status"

manifest_temp="$work_dir/SHA256SUMS"
(
    cd "$output_dir"
    rg --files --hidden --no-ignore -0 | LC_ALL=C sort -z | xargs -0 sha256sum
) >"$manifest_temp"
cp "$manifest_temp" "$output_dir/SHA256SUMS"
chmod -R a-w "$output_dir"
echo "CHECK=PASS output=$output_dir"
