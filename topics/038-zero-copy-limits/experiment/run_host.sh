#!/usr/bin/env bash
set -euo pipefail

# This runner is GNU/Linux-specific. It requires an archive of a committed
# source candidate and writes every result outside that source tree.
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
        PYTHONPATH | PYTHONHOME | RIPGREP_CONFIG_PATH | CDPATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
export GIT_NO_REPLACE_OBJECTS=1

if [[ $# -ne 4 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 SOURCE_ARCHIVE" >&2
    exit 2
fi
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to xxl or the authorized Arm hostname}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the runtime-resolved hostname}"

output_dir=$(realpath -m -- "$1")
source_commit=${2,,}
archive_digest_expected=${3,,}
source_archive=$(realpath -m -- "$4")
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "SOURCE_COMMIT must be a full 40-hex Git object ID" >&2
    exit 2
fi
if [[ ! $archive_digest_expected =~ ^[0-9a-f]{64}$ ]]; then
    echo "SOURCE_ARCHIVE_SHA256 must be 64 hexadecimal digits" >&2
    exit 2
fi
if [[ -e $output_dir || -e ${output_dir}.work ]]; then
    echo "output or work path already exists: $output_dir" >&2
    exit 2
fi
if [[ ! -f $source_archive ]]; then
    echo "source archive does not exist: $source_archive" >&2
    exit 2
fi
archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $archive_digest != "$archive_digest_expected" ]]; then
    echo "source archive digest mismatch" >&2
    exit 2
fi
# A digest binds this run to archive bytes but not to SOURCE_COMMIT. A
# commit-created `git archive` stores the commit ID as the pax global header
# comment in the first tar data block; require it to match SOURCE_COMMIT so the
# receipt's source identity is the archive's own claim, not the caller's.
pax_global_header=$(gzip -dc -- "$source_archive" 2>/dev/null | dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_global_header =~ comment=([0-9a-f]{40}) ]]; then
    echo "source archive does not embed a commit ID; create it with git archive --format=tar.gz COMMIT" >&2
    exit 2
fi
if [[ ${BASH_REMATCH[1]} != "$source_commit" ]]; then
    echo "source archive embeds commit ${BASH_REMATCH[1]}, not SOURCE_COMMIT $source_commit" >&2
    exit 2
fi
if tar -tzf "$source_archive" | rg '(^/|(^|/)\.\.(/|$))'; then
    echo "source archive contains an unsafe path" >&2
    exit 2
fi

resolved_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $resolved_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    echo "resolved host mismatch: expected $SSH_RESOLVED_HOSTNAME, got $resolved_hostname" >&2
    exit 1
fi
case $SSH_TARGET_LABEL in
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

work_dir="${output_dir}.work"
extract_dir="$work_dir/archive"
mkdir -p "$output_dir" "$extract_dir"
filesystem_type=$(findmnt -no FSTYPE -T "$work_dir")
if [[ $filesystem_type != tmpfs ]]; then
    echo "focused experiment requires warmed tmpfs; $work_dir is $filesystem_type" >&2
    # Remove the just-created empty directories so a corrected rerun does not
    # fail the exists-check above; rmdir cannot touch non-empty evidence.
    rmdir -- "$extract_dir" "$work_dir" "$output_dir"
    exit 1
fi
tar -xzf "$source_archive" -C "$extract_dir"
if [[ -n $(find "$extract_dir" -type l -print -quit) ]]; then
    echo "source archive contains a symbolic link" >&2
    exit 2
fi

runner_relative=topics/038-zero-copy-limits/experiment/run_host.sh
mapfile -t runner_markers < <(find "$extract_dir" -type f -path "*/$runner_relative" | LC_ALL=C sort)
if [[ ${#runner_markers[@]} -ne 1 ]]; then
    echo "archive must contain exactly one Topic 38 host runner" >&2
    exit 2
fi
source_root=${runner_markers[0]%/"$runner_relative"}
source_root=$(realpath "$source_root")
experiment_dir="$source_root/topics/038-zero-copy-limits/experiment"
if ! cmp -- "${BASH_SOURCE[0]}" "$experiment_dir/run_host.sh"; then
    echo "executed host runner differs from the source archive" >&2
    exit 2
fi

write_source_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum
    ) >"$destination"
}

run_gate() {
    local name=$1
    shift
    {
        echo "COMMAND=$*"
        "$@"
    } >"$output_dir/$name" 2>&1
}

record_optional() {
    local name=$1
    shift
    {
        echo "COMMAND=$*"
        "$@"
    } >"$output_dir/$name" 2>&1 || true
}

write_source_manifest "$output_dir/source-manifest-before.sha256"
{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive=%s\n' "$source_archive"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'source_root=%s\n' "$source_root"
    printf 'runner_sha256='; sha256sum "$experiment_dir/run_host.sh" | awk '{print $1}'
    printf 'swept_environment_names=%s\n' "${swept_environment_names[*]:-none}"
} >"$output_dir/source-identity.txt"

{
    printf 'date_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'hostname_short='; hostname
    printf 'hostname_fqdn=%s\n' "$resolved_hostname"
    printf 'uname_all='; uname -a
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel='; uname -r
    printf 'cpu_count_online='; getconf _NPROCESSORS_ONLN
    printf 'nproc_available='; nproc
    printf 'page_size='; getconf PAGESIZE
    printf 'affinity='; taskset -pc $$ | awk -F: '{gsub(/^ +/, "", $2); print $2}'
    printf 'payload_filesystem=%s\n' "$filesystem_type"
    printf 'build_flags=-O3 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer\n'
    printf 'native_build_extra=-march=native\n'
    printf 'transfer_bytes=536870912\n'
    printf 'correctness_bytes=16777219\n'
    printf 'requested_chunk_bytes=262144\n'
    printf 'schedule_seed=38017\n'
    printf 'blocks_per_pair=8\n'
    printf 'fresh_process_runs=96\n'
    printf '%s\n' \
        'transfer_timer_boundary=start_after_file_open_and_sender_connect_without_receiver_ready_barrier_end_after_shutdown_report_and_waitpid_buffered_alloc_free_and_splice_pipe_create_close_included_sender_cpu_interval_receiver_cpu_whole_child'
    printf 'msg_zerocopy_boundary=correctness_and_completion_only_no_timing_ranking\n'
    lscpu
} >"$output_dir/host.txt" 2>&1

record_optional proc-cpuinfo.txt sed -n '1,240p' /proc/cpuinfo
record_optional proc-self-status.txt sed -n '1,240p' /proc/self/status
record_optional cgroup.txt sh -c 'printf "self_cgroup="; cat /proc/self/cgroup; printf "cpu_pressure="; cat /proc/pressure/cpu'
record_optional rustc-version.txt rustc -vV
record_optional cargo-version.txt cargo -Vv
record_optional python-version.txt python3 -VV
record_optional cc-version.txt cc -v
record_optional linker-version.txt ld --version
record_optional binutils-version.txt objdump --version
record_optional rust-target-cfg.txt rustc --print cfg
record_optional cc-native-target.txt cc -march=native -Q --help=target
record_optional kernel-zero-copy-doc-presence.txt test -r /proc/sys/net/core/optmem_max
record_optional network-sysctls.txt sh -c 'printf "optmem_max="; cat /proc/sys/net/core/optmem_max; printf "tcp_wmem="; cat /proc/sys/net/ipv4/tcp_wmem; printf "tcp_rmem="; cat /proc/sys/net/ipv4/tcp_rmem'
record_optional limits.txt sh -c 'ulimit -a; printf "memlock_kib="; ulimit -l'

cargo_target="$work_dir/cargo-target"
native_cargo_target="$work_dir/cargo-target-native"
run_gate gate-cargo-fmt.txt env CARGO_TARGET_DIR="$cargo_target" cargo fmt --manifest-path "$source_root/Cargo.toml" --all -- --check
run_gate gate-cargo-test-lib-examples.txt env CARGO_TARGET_DIR="$cargo_target" cargo test --manifest-path "$source_root/Cargo.toml" --locked --workspace --lib --examples
run_gate gate-cargo-test-doc.txt env CARGO_TARGET_DIR="$cargo_target" cargo test --manifest-path "$source_root/Cargo.toml" --locked --workspace --doc
# The repository-wide clippy gate runs on the pinned local toolchain before
# archival.  Restrict the host replay to this topic because newer host rustc
# versions can introduce warnings in unrelated historical benchmark targets.
run_gate gate-cargo-clippy.txt env CARGO_TARGET_DIR="$cargo_target" cargo clippy --manifest-path "$source_root/Cargo.toml" --locked --package zero-copy-limits --all-targets -- -D warnings
run_gate gate-cargo-bench-build.txt env CARGO_TARGET_DIR="$cargo_target" cargo bench --manifest-path "$source_root/Cargo.toml" --locked --workspace --no-run
run_gate gate-cargo-doc.txt env CARGO_TARGET_DIR="$cargo_target" RUSTDOCFLAGS='-D warnings' cargo doc --manifest-path "$source_root/Cargo.toml" --locked --workspace --no-deps
run_gate build-rust-generic.txt env CARGO_TARGET_DIR="$cargo_target" RUSTFLAGS='' cargo build --manifest-path "$source_root/Cargo.toml" --locked --release --package zero-copy-limits
run_gate rust-contract-generic.txt "$cargo_target/release/zero-copy-contract-probe" verify
run_gate build-rust-native.txt env CARGO_TARGET_DIR="$native_cargo_target" RUSTFLAGS='-C target-cpu=native' cargo build --manifest-path "$source_root/Cargo.toml" --locked --release --package zero-copy-limits
run_gate rust-contract-native.txt "$native_cargo_target/release/zero-copy-contract-probe" verify

build_dir="$work_dir/c-build"
run_gate build-c-probes.txt "$experiment_dir/build_probe.sh" "$build_dir"

generic_payload="$work_dir/generic-correctness.bin"
"$build_dir/transfer-probe" prepare "$generic_payload" 16777219 >"$output_dir/generic-prepare.txt" 2>&1
"$build_dir/transfer-probe" warm "$generic_payload" >"$output_dir/generic-warm.txt" 2>&1
for method in buffered sendfile splice; do
    run_gate "generic-correctness-${method}.txt" \
        "$build_dir/transfer-probe" run "$method" "$generic_payload" 16777219 1 262144
done

benchmark_dir="$output_dir/benchmark"
payload="$work_dir/transfer-payload.bin"
run_gate run-processes.txt python3 -I -B "$experiment_dir/run_processes.py" \
    --binary "$build_dir/transfer-probe-native" \
    --payload "$payload" \
    --output "$benchmark_dir" \
    --bytes 536870912 \
    --correctness-bytes 16777219 \
    --chunk 262144 \
    --seed 38017 \
    --blocks 8

run_gate msgzc-generic-run.txt "$build_dir/msgzc-control"
cp "$output_dir/msgzc-generic-run.txt" "$benchmark_dir/msgzc-generic.stdout"
: >"$benchmark_dir/msgzc-generic.stderr"
run_gate msgzc-native-run.txt "$build_dir/msgzc-control-native"
cp "$output_dir/msgzc-native-run.txt" "$benchmark_dir/msgzc-native.stdout"
: >"$benchmark_dir/msgzc-native.stderr"

run_gate analyze.txt python3 -I -B "$experiment_dir/analyze.py" \
    "$benchmark_dir/runs.tsv" \
    --summary "$benchmark_dir/summary.tsv" \
    --contrasts "$benchmark_dir/contrasts.tsv"

artifacts="$benchmark_dir/artifacts"
mkdir "$artifacts"
cp "$experiment_dir/transfer_bench.c" "$artifacts/"
cp "$experiment_dir/msgzc_control.c" "$artifacts/"
cp "$experiment_dir/schedule.py" "$artifacts/"
cp "$experiment_dir/run_processes.py" "$artifacts/"
cp "$experiment_dir/analyze.py" "$artifacts/"
cp "$experiment_dir/validate_receipts.py" "$artifacts/"
cp "$build_dir/transfer-probe" "$artifacts/"
cp "$build_dir/transfer-probe-native" "$artifacts/"
cp "$build_dir/msgzc-control" "$artifacts/"
cp "$build_dir/msgzc-control-native" "$artifacts/"
(
    cd "$artifacts"
    sha256sum * | LC_ALL=C sort
) >"$benchmark_dir/artifacts.sha256"

codegen="$output_dir/codegen"
mkdir "$codegen"

retain_linked_calls() {
    local disassembly=$1
    local destination=$2
    local targets=$3

    # A linked call site has a call instruction (`call`/`callq` on x86-64 or
    # `bl` on AArch64) and a resolved symbol.  This excludes PLT labels and
    # relocation/reference-only lines from the retained receipt.
    rg -n "[[:space:]](callq?|bl)[[:space:]]+[^<]*<(${targets})(@[^>]*)?>" \
        "$disassembly" >"$destination" || true
}

require_linked_call_count() {
    local receipt=$1
    local symbol=$2
    local minimum=$3
    local count

    count=$(rg -c "<${symbol}(@[^>]*)?>" "$receipt" || true)
    count=${count:-0}
    if ((count < minimum)); then
        echo "codegen gate: expected at least $minimum linked call(s) to $symbol in $receipt; found $count" >&2
        return 1
    fi
}

for flavor in generic native; do
    if [[ $flavor == generic ]]; then
        transfer_binary="$build_dir/transfer-probe"
        msgzc_binary="$build_dir/msgzc-control"
    else
        transfer_binary="$build_dir/transfer-probe-native"
        msgzc_binary="$build_dir/msgzc-control-native"
    fi
    objdump -drwC "$transfer_binary" >"$codegen/transfer-${flavor}.txt"
    objdump -drwC "$msgzc_binary" >"$codegen/msgzc-${flavor}.txt"
    transfer_calls="$codegen/transfer-${flavor}-call-sites.txt"
    msgzc_calls="$codegen/msgzc-${flavor}-call-sites.txt"
    retain_linked_calls "$codegen/transfer-${flavor}.txt" "$transfer_calls" \
        'pread|send|sendfile|splice'
    retain_linked_calls "$codegen/msgzc-${flavor}.txt" "$msgzc_calls" \
        'setsockopt|sendmsg|recvmsg'
    require_linked_call_count "$transfer_calls" pread 1
    require_linked_call_count "$transfer_calls" send 1
    require_linked_call_count "$transfer_calls" sendfile 1
    require_linked_call_count "$transfer_calls" splice 2
    require_linked_call_count "$msgzc_calls" setsockopt 1
    require_linked_call_count "$msgzc_calls" sendmsg 1
    require_linked_call_count "$msgzc_calls" recvmsg 1
done

run_gate validate.txt python3 -I -B "$experiment_dir/validate_receipts.py" \
    "$benchmark_dir" --binary "$build_dir/transfer-probe-native"
write_source_manifest "$output_dir/source-manifest-after.sha256"
cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"

{
    printf 'status=PASS\n'
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'architecture=%s\n' "$architecture"
    printf 'filesystem_type=%s\n' "$filesystem_type"
    printf 'process_runs=96\n'
    printf 'blocks_per_pair=8\n'
    printf 'correctness=buffered_sendfile_splice_exact_bytes\n'
    printf 'msg_zerocopy=completion_coverage_8_of_8\n'
    cat "$output_dir/analyze.txt"
} >"$output_dir/SUMMARY.txt"

(
    cd "$output_dir"
    find . -type f ! -name MANIFEST.sha256 -print0 | LC_ALL=C sort -z | xargs -0 sha256sum
) >"$output_dir/MANIFEST.sha256"
printf 'HOST_RUN=PASS output=%s\n' "$output_dir"
