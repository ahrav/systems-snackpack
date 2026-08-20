#!/usr/bin/env -S bash -p
set -euo pipefail

# Run the committed Topic 40 probe from a digest-bound Git archive. The probe
# exercises correctness and code-generation contracts; it reports no timing.
#
# Privileged mode (-p) makes Bash skip the $BASH_ENV and $ENV startup files
# and refuse to import shell functions from the environment, so a hostile
# environment cannot execute code before the first command of this script.
# The $- gate rejects any launch that dropped -p (for example
# `bash run_host.sh`), so every accepted execution started uncontaminated.
if [[ $- != *p* ]]; then
    echo "exact-source experiment requires bash privileged mode: run via ./run_host.sh or bash -p" >&2
    exit 2
fi
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source experiment refuses BASH_ENV" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source experiment refuses inherited shell functions" >&2
    exit 2
fi
if [[ -s /etc/ld.so.preload ]]; then
    echo "exact-source experiment refuses system-wide dynamic-loader preloads" >&2
    exit 2
fi

swept_environment_names=()
while IFS= read -r variable; do
    case $variable in
    BPFTOOL_* | CLANG_* | LLVM_* | \
        RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTDOC | RUSTFMT | \
        RUSTFLAGS | RUSTDOCFLAGS | CARGO_ENCODED_RUSTFLAGS | CARGO_INCREMENTAL | \
        CARGO_BUILD_* | CARGO_TARGET_* | CARGO_PROFILE_* | CARGO_UNSTABLE_* | \
        CC | CFLAGS | CPPFLAGS | LDFLAGS | COMPILER_PATH | GCC_EXEC_PREFIX | \
        LIBRARY_PATH | CPATH | C_INCLUDE_PATH | CPLUS_INCLUDE_PATH | \
        LD_* | DYLD_* | GLIBC_TUNABLES | MALLOC_* | \
        GIT_* | TAR_OPTIONS | TAPE | GZIP | \
        PYTHONPATH | PYTHONHOME | PYTHONSTARTUP | PYTHONINSPECT | \
        RIPGREP_CONFIG_PATH | CDPATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
export GIT_NO_REPLACE_OBJECTS=1
export LANG=C
export LC_ALL=C
export PATH="$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
hash -r

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
expected_source_sha256=faab623812e641585f0c4fa56fd74f9801faa4dde84f4d20431a0a3eb72cf8e8
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

work_dir="${output_dir}.work"
extract_dir="$work_dir/archive"
output_parent=$(dirname -- "$output_dir")
if [[ -L $output_parent || ! -d $output_parent ]]; then
    echo "output parent must already exist as a real directory: $output_parent" >&2
    exit 2
fi
invoking_uid=$(id -u)
probe_directory=$output_parent
while :; do
    if [[ -L $probe_directory ]]; then
        echo "output ancestor must not be a symbolic link: $probe_directory" >&2
        exit 2
    fi
    ancestor_owner=$(stat -c %u -- "$probe_directory")
    ancestor_mode=$(stat -c %a -- "$probe_directory")
    if [[ $ancestor_owner != "$invoking_uid" && $ancestor_owner != 0 ]]; then
        echo "output ancestor must be owned by the invoking user or root: $probe_directory" >&2
        exit 2
    fi
    if ((0$ancestor_mode & 022)) && ((!(0$ancestor_mode & 01000))); then
        echo "output ancestor is writable by others and not sticky: $probe_directory" >&2
        exit 2
    fi
    [[ $probe_directory == / ]] && break
    probe_directory=$(dirname -- "$probe_directory")
done
mkdir -m 0700 -- "$output_dir"
mkdir -m 0700 -- "$work_dir"
mkdir -m 0700 -- "$extract_dir"

# Snapshot the caller's archive once so replacement after the digest check
# cannot alter extraction.
private_archive="$work_dir/source-archive.tar.gz"
cp -- "$source_archive" "$private_archive"
chmod 0400 "$private_archive"
source_archive=$private_archive
archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $archive_digest != "$archive_digest_expected" ]]; then
    echo "source archive digest mismatch" >&2
    exit 2
fi
pax_global_header=$(gzip -dc -- "$source_archive" 2>/dev/null | dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_global_header =~ comment=([0-9a-f]{40}) ]]; then
    echo "archive lacks the commit identity written by git archive" >&2
    exit 2
fi
if [[ ${BASH_REMATCH[1]} != "$source_commit" ]]; then
    echo "archive embeds ${BASH_REMATCH[1]}, not $source_commit" >&2
    exit 2
fi
if tar -tzf "$source_archive" | rg '(^/|(^|/)\.\.(/|$))'; then
    echo "source archive contains an unsafe path" >&2
    exit 2
fi
if tar -tvzf "$source_archive" | awk 'substr($1, 1, 1) ~ /^[lh]$/ { found=1 } END { exit !found }'; then
    echo "source archive contains a symbolic or hard link" >&2
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
    jit_objdump_machine=i386:x86-64
    ;;
dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
    # The Arm label names one specific host, so the label must equal the
    # locally resolved hostname; architecture alone would certify any
    # AArch64 machine as the named host.
    [[ $resolved_hostname == "$SSH_TARGET_LABEL" ]] || {
        echo "fixed Arm label must match the resolved hostname; got $resolved_hostname" >&2
        exit 1
    }
    [[ $architecture == aarch64 || $architecture == arm64 ]] || {
        echo "authorized Arm host must be aarch64/arm64; got $architecture" >&2
        exit 1
    }
    jit_objdump_machine=aarch64
    ;;
*)
    echo "unexpected SSH target label: $SSH_TARGET_LABEL" >&2
    exit 2
    ;;
esac

tar -xzf "$source_archive" -C "$extract_dir"
runner_relative=topics/040-ebpf-internals/experiment/run_host.sh
mapfile -t runner_markers < <(
    rg --files --hidden --no-ignore "$extract_dir" |
        rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#runner_markers[@]} -ne 1 ]]; then
    echo "archive must contain exactly one Topic 40 host runner" >&2
    exit 2
fi
source_root=${runner_markers[0]%/"$runner_relative"}
source_root=$(realpath "$source_root")
experiment_dir="$source_root/topics/040-ebpf-internals/experiment"
if ! cmp -- "${BASH_SOURCE[0]}" "$experiment_dir/run_host.sh"; then
    echo "executed host runner differs from the archive's runner" >&2
    exit 2
fi
if [[ $(sha256sum "$experiment_dir/ebpf_socket_filter.c" | awk '{print $1}') != "$expected_source_sha256" ]]; then
    echo "committed C probe differs from the exact tested source" >&2
    exit 2
fi

write_source_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum --
    ) >"$destination"
}

run_gate() {
    local name=$1
    shift
    {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1
}

record_required() {
    local name=$1
    shift
    if ! {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1; then
        echo "required host metadata probe failed: $name" >&2
        exit 1
    fi
}

record_optional() {
    local name=$1
    shift
    {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1 || true
}

write_source_manifest "$output_dir/source-manifest-before.sha256"
{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive=%s\n' "$source_archive"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'source_root=%s\n' "$source_root"
    printf 'probe_source_sha256=%s\n' "$expected_source_sha256"
    printf 'runner_sha256='; sha256sum "$experiment_dir/run_host.sh" | awk '{print $1}'
    printf 'contract_sha256='; sha256sum "$experiment_dir/expected_patterns.json" | awk '{print $1}'
    printf 'swept_environment_names=%s\n' "${swept_environment_names[*]:-none}"
} >"$output_dir/source-identity.txt"

{
    printf 'date_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_target_label_trust=caller_supplied_and_allowlisted\n'
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'ssh_resolved_hostname_trust=caller_supplied_compared_to_local_hostname_fqdn\n'
    printf 'hostname_short='; hostname
    printf 'hostname_fqdn=%s\n' "$resolved_hostname"
    printf 'uname_all='; uname -a
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel='; uname -r
    printf 'cpu_count_online='; getconf _NPROCESSORS_ONLN
    printf 'cpu_count_configured='; getconf _NPROCESSORS_CONF
    printf 'cpu_count_available='; nproc
    printf 'cpu_list_online='; cat /sys/devices/system/cpu/online
    printf 'cpu_list_possible='; cat /sys/devices/system/cpu/possible
    printf 'cpu_list_present='; cat /sys/devices/system/cpu/present
    printf 'page_size='; getconf PAGESIZE
    printf 'build_flags=-O2 -g -std=c11 -Wall -Wextra -Werror\n'
    printf 'probe_source_sha256=%s\n' "$expected_source_sha256"
    printf 'ordinary_processes=1 expected_exit=77\n'
    printf 'fresh_privileged_processes=8\n'
    printf 'privileged_command=sudo -n BINARY OUTPUT_DIRECTORY\n'
    printf 'measurement_kind=correctness and generated-code inspection only\n'
    printf 'timing_reported=no\n'
    printf 'drop_poll_timeout_ms=250 correctness_threshold_not_latency\n'
    lscpu
} >"$output_dir/host.txt" 2>&1

record_required proc-cpuinfo.txt sed -n '1,320p' /proc/cpuinfo
record_required proc-self-status.txt sed -n '1,260p' /proc/self/status
record_required gcc-version.txt gcc -v
record_required gcc-target.txt gcc -dumpmachine
record_required gcc-target-options.txt gcc -Q -O2 --help=target
record_required rustc-version.txt rustc -vV
record_required cargo-version.txt cargo -Vv
record_required python-version.txt python3 -VV
record_required objdump-version.txt objdump --version
record_required readelf-version.txt readelf --version
record_required sudo-version.txt sudo -V
record_optional clang-version.txt clang --version
record_optional bpftool-version.txt bpftool version

kernel_config_decoded="$work_dir/kernel-config-decoded.txt"
kernel_release=$(uname -r)
if [[ -r /proc/config.gz ]]; then
    gzip -dc /proc/config.gz >"$kernel_config_decoded"
    kernel_config_source=/proc/config.gz
elif [[ -r /boot/config-$kernel_release ]]; then
    cp -- "/boot/config-$kernel_release" "$kernel_config_decoded"
    kernel_config_source="/boot/config-$kernel_release"
elif sudo -n -- /usr/bin/cat "/boot/config-$kernel_release" >"$kernel_config_decoded" 2>/dev/null; then
    kernel_config_source="sudo:/boot/config-$kernel_release"
else
    echo "required kernel configuration is unavailable" >&2
    exit 1
fi
if [[ ! -s $kernel_config_decoded ]]; then
    echo "kernel configuration decoded empty" >&2
    exit 1
fi
kernel_symbols=(
    BPF BPF_SYSCALL BPF_JIT BPF_JIT_ALWAYS_ON BPF_UNPRIV_DEFAULT_OFF
    CGROUP_BPF XDP_SOCKETS DEBUG_INFO_BTF NET_CLS_BPF NET_ACT_BPF
)
{
    printf 'kernel_config_source=%s\n' "$kernel_config_source"
    printf 'kernel_config_symbol_states_begin\n'
    for symbol in "${kernel_symbols[@]}"; do
        if symbol_line=$(rg -N -m 1 "^CONFIG_${symbol}=" "$kernel_config_decoded"); then
            printf '%s\n' "$symbol_line"
        elif rg -N -q "^# CONFIG_${symbol} is not set\$" "$kernel_config_decoded"; then
            printf 'CONFIG_%s=not_set\n' "$symbol"
        else
            printf 'CONFIG_%s=absent\n' "$symbol"
        fi
    done
    printf 'kernel_config_symbol_states_end\n'
} >"$output_dir/kernel-bpf-config.txt"

read_policy_value() {
    local path=$1
    if [[ -r $path ]]; then
        cat "$path"
    else
        sudo -n -- /usr/bin/cat "$path"
    fi
}
{
    printf 'kernel.unprivileged_bpf_disabled='; read_policy_value /proc/sys/kernel/unprivileged_bpf_disabled
    printf 'net.core.bpf_jit_enable='; read_policy_value /proc/sys/net/core/bpf_jit_enable
    printf 'net.core.bpf_jit_harden='; read_policy_value /proc/sys/net/core/bpf_jit_harden
    printf 'kernel.bpf_stats_enabled='; read_policy_value /proc/sys/kernel/bpf_stats_enabled
    printf 'login_capability_lines_begin\n'
    rg -N '^Cap(Inh|Prm|Eff|Bnd|Amb):' /proc/self/status
    printf 'login_capability_lines_end\n'
} >"$output_dir/bpf-policy.txt" 2>&1

{
    printf 'bpffs_mounts_begin\n'
    findmnt -rn -t bpf || true
    printf 'bpffs_mounts_end\n'
    printf 'vmlinux_btf='; stat -c 'path=%n bytes=%s mode=%a owner=%U:%G' /sys/kernel/btf/vmlinux
    printf 'kernel_lockdown='; cat /sys/kernel/security/lockdown 2>/dev/null || printf 'unavailable\n'
} >"$output_dir/bpf-filesystems.txt" 2>&1

artifacts="$output_dir/artifacts"
mkdir -m 0700 "$artifacts"
cp -- "$experiment_dir/ebpf_socket_filter.c" "$artifacts/"
cp -- "$experiment_dir/expected_patterns.json" "$artifacts/"
cp -- "$experiment_dir/run_processes.py" "$artifacts/"
cp -- "$experiment_dir/validate_receipts.py" "$artifacts/"
cp -- "$experiment_dir/run_host.sh" "$artifacts/"

build_dir="$work_dir/build"
mkdir -m 0700 "$build_dir"
probe_binary="$build_dir/ebpf-socket-filter"
run_gate build.txt gcc -v -O2 -g -std=c11 -Wall -Wextra -Werror \
    "$experiment_dir/ebpf_socket_filter.c" -o "$probe_binary"
run_gate rust-tests.txt cargo test --locked --manifest-path "$source_root/Cargo.toml" \
    --package ebpf-internals --lib --examples
run_gate rust-example.txt cargo run --locked --manifest-path "$source_root/Cargo.toml" \
    --package ebpf-internals --example cost-and-control
cp -- "$probe_binary" "$artifacts/ebpf-socket-filter"
chmod 0500 "$artifacts/ebpf-socket-filter"

codegen="$output_dir/codegen"
jit_codegen="$codegen/jit"
mkdir -m 0700 "$codegen" "$jit_codegen"
run_gate codegen/probe.objdump.txt objdump -drwC "$artifacts/ebpf-socket-filter"
run_gate codegen/probe.elf.txt readelf -h -n -A "$artifacts/ebpf-socket-filter"

ordinary="$output_dir/ordinary"
mkdir -m 0700 "$ordinary"
set +e
"$artifacts/ebpf-socket-filter" "$ordinary/kernel-bytes" \
    >"$ordinary/run.stdout" 2>"$ordinary/run.stderr"
ordinary_return_code=$?
set -e
printf '%s\n' "$ordinary_return_code" >"$ordinary/return-code.txt"
{
    printf 'COMMAND=%q %q\n' "$artifacts/ebpf-socket-filter" "$ordinary/kernel-bytes"
    printf 'return_code=%s\n' "$ordinary_return_code"
    printf 'expected_boundary=permission_policy_before_verifier_diagnostics\n'
} >"$ordinary/run-command.txt"
if [[ $ordinary_return_code -ne 77 ]]; then
    echo "ordinary BPF load did not reach the expected permission boundary" >&2
    exit 1
fi

sudo_path=$(command -v sudo)
chown_path=$(command -v chown)
run_gate run-privileged-processes.txt python3 -I -B "$experiment_dir/run_processes.py" \
    --binary "$artifacts/ebpf-socket-filter" \
    --contract "$experiment_dir/expected_patterns.json" \
    --output "$output_dir/processes" \
    --sudo "$sudo_path" \
    --chown "$chown_path" \
    --runs 8

for ((sequence = 1; sequence <= 8; sequence += 1)); do
    printf -v sequence_label '%02d' "$sequence"
    for label in accept drop; do
        blob="$output_dir/processes/raw/run-${sequence_label}-kernel-bytes/${label}.jited.bin"
        destination="$jit_codegen/run-${sequence_label}-${label}.objdump.txt"
        objdump -D -b binary -m "$jit_objdump_machine" "$blob" >"$destination"
        if [[ ! -s $destination ]] || ! rg -q '\bret[q]?\b' "$destination"; then
            echo "JIT disassembly lacks a return instruction: $destination" >&2
            exit 1
        fi
    done
done

write_source_manifest "$output_dir/source-manifest-after.sha256"
cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"
run_gate validate-receipts.txt python3 -I -B "$experiment_dir/validate_receipts.py" \
    --root "$output_dir" \
    --contract "$experiment_dir/expected_patterns.json"
(
    cd "$artifacts"
    rg --files -0 | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$output_dir/artifacts.sha256"

{
    printf 'status=PASS\n'
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'architecture=%s\n' "$architecture"
    printf 'ordinary_permission_processes=1\n'
    printf 'fresh_privileged_processes=8\n'
    printf 'jit_disassemblies=16\n'
    printf 'timing_reported=no\n'
} >"$output_dir/status.txt"
(
    cd "$output_dir"
    rg --files -g '!bundle-manifest.sha256' -0 |
        LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$output_dir/bundle-manifest.sha256"

printf 'experiment_status=PASS output=%s\n' "$output_dir"
