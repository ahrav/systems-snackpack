#!/usr/bin/env bash
set -euo pipefail

# Build and run Topic 26 on one Linux host, retaining a sealed evidence bundle.

if (($# != 2)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY\n' "$0" >&2
    exit 2
fi
if [[ "$(uname -s)" != Linux ]]; then
    printf 'Topic 26 can run only on Linux\n' >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$(realpath -m -- "$2")"
topic_rel="topics/026-nic-datapath"
experiment_rel="$topic_rel/experiment"
experiment_dir="$repo_root/$experiment_rel"
source_archive_paths=(Cargo.toml Cargo.lock "$topic_rel")

for tool in \
    awk bash cargo cat cc cmp date getconf git gzip hostname lscpu mkdir mktemp mv \
    nm objdump python3 readelf realpath rg rustc sha256sum sort tar timeout uname \
    xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done
for source in udp_batch.c run_processes.py validate_receipts.py run_host.sh; do
    if [[ ! -r "$experiment_dir/$source" ]]; then
        printf 'required experiment file is unavailable: %s\n' "$source" >&2
        exit 2
    fi
done
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi
if [[ -e "$output_dir" ]] \
    && [[ -n "$(rg --files -uu "$output_dir" 2>/dev/null || true)" ]]; then
    printf 'OUTPUT_DIRECTORY must be absent or empty: %s\n' "$output_dir" >&2
    exit 2
fi
mkdir -p -- "$output_dir"

scratch_dir="$(mktemp -d)"
scratch_dir="$(cd -- "$scratch_dir" && pwd -P)"
if [[ "$scratch_dir" == "$repo_root" || "$scratch_dir" == "$repo_root"/* \
    || "$scratch_dir" == "$output_dir" || "$scratch_dir" == "$output_dir"/* \
    || "$repo_root" == "$scratch_dir"/* || "$output_dir" == "$scratch_dir"/* ]]; then
    printf 'scratch directory overlaps source or evidence directory\n' >&2
    rm -rf -- "$scratch_dir"
    exit 2
fi

scan_source_paths() {
    (
        cd "$repo_root"
        rg --files -uu -g '!.git/**' -g '!target/**' -0 | sort -z
    )
}

source_manifest() {
    (
        cd "$repo_root"
        scan_source_paths | xargs -0 sha256sum --
    )
}

seal_evidence() {
    local status="$1"
    local source_status="$2"
    printf 'exit=%s\nsource_manifest=%s\n' "$status" "$source_status" \
        >"$output_dir/run.status"
    (
        cd "$output_dir"
        rg --files -uu -g '!evidence.sha256' -0 . \
            | sort -z \
            | xargs -0 sha256sum --
    ) >"$scratch_dir/evidence.sha256"
    mv -- "$scratch_dir/evidence.sha256" "$output_dir/evidence.sha256"
}

finalize() {
    local status="$?"
    trap - EXIT
    set +e
    local source_status=not-started
    if [[ -r "$output_dir/source-files.before.sha256" ]]; then
        source_manifest >"$output_dir/source-files.after.sha256"
        if cmp -s "$output_dir/source-files.before.sha256" \
            "$output_dir/source-files.after.sha256"; then
            source_status=match
        else
            source_status=mismatch
            if ((status == 0)); then
                status=1
            fi
        fi
    fi
    printf 'utc_end=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        >>"$output_dir/host.txt" 2>/dev/null || true
    seal_evidence "$status" "$source_status"
    local seal_status="$?"
    rm -rf -- "$scratch_dir"
    if ((seal_status != 0 && status == 0)); then
        status=1
    fi
    exit "$status"
}
trap finalize EXIT

if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" \
    != "$repo_root" ]]; then
    printf 'REPOSITORY_ROOT must be a Git worktree root\n' >&2
    exit 2
fi
source_commit="$(git -C "$repo_root" rev-parse HEAD)"
source_tree="$(git -C "$repo_root" rev-parse 'HEAD^{tree}')"
source_branch="$(git -C "$repo_root" branch --show-current)"
worktree_status="$(git -C "$repo_root" status --porcelain --untracked-files=all)"
if [[ -n "$worktree_status" ]]; then
    printf 'repository must be clean before evidence collection\n%s\n' \
        "$worktree_status" >&2
    exit 2
fi

source_manifest >"$output_dir/source-files.before.sha256"
git -C "$repo_root" archive --format=tar "$source_commit" -- \
    "${source_archive_paths[@]}" \
    >"$scratch_dir/source.tar"
gzip -n -9 <"$scratch_dir/source.tar" >"$output_dir/source.tar.gz"
(cd "$output_dir" && sha256sum source.tar.gz) >"$output_dir/source-archive.sha256"

swept_variables=()
while IFS= read -r variable; do
    case "$variable" in
        CC | CFLAGS | CPPFLAGS | LDFLAGS | CPATH | C_INCLUDE_PATH \
            | CPLUS_INCLUDE_PATH | COMPILER_PATH | GCC_EXEC_PREFIX \
            | LD_LIBRARY_PATH | LIBRARY_PATH | PYTHONHOME | PYTHONPATH \
            | PYTHONSTARTUP | LD_PRELOAD | LD_AUDIT | GLIBC_TUNABLES \
            | MALLOC_ARENA_MAX | RUSTFLAGS | CARGO_BUILD_RUSTFLAGS \
            | CARGO_ENCODED_RUSTFLAGS | CARGO_TARGET_DIR | CARGO_BUILD_TARGET \
            | RUSTC | RUSTC_WRAPPER | RUSTDOC | RUSTDOCFLAGS)
            swept_variables+=("$variable")
            unset "$variable"
            ;;
    esac
done < <(compgen -e)
# Importing run_processes from the validator must not dirty the source tree.
export PYTHONDONTWRITEBYTECODE=1

{
    printf 'utc_start=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'hostname=%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'invocation_target_alias=%s\n' \
        "${TOPIC26_TARGET_ALIAS:-unrecorded}"
    printf 'invocation_resolved_host=%s\n' \
        "${TOPIC26_RESOLVED_HOST:-unrecorded}"
    printf 'source_commit=%s\nsource_tree=%s\nsource_branch=%s\n' \
        "$source_commit" "$source_tree" "$source_branch"
    printf 'swept_environment=%s\n' "${swept_variables[*]:-none}"
    printf 'architecture=%s\nkernel=%s\n' "$(uname -m)" "$(uname -r)"
    printf 'online_cpu_count=%s\nconfigured_cpu_count=%s\n' \
        "$(getconf _NPROCESSORS_ONLN)" "$(getconf _NPROCESSORS_CONF)"
    printf 'cpus_allowed_list=%s\nmems_allowed_list=%s\n' \
        "$(awk '/^Cpus_allowed_list:/ {print $2}' /proc/self/status)" \
        "$(awk '/^Mems_allowed_list:/ {print $2}' /proc/self/status)"

    printf '\nuname\n'
    uname -a
    printf '\ncompiler\n'
    cc --version
    printf 'compiler_target=%s\n' "$(cc -dumpmachine)"
    printf '\ncompiler_target_options\n'
    cc -Q -march=native --help=target 2>&1 || true
    printf '\nrustc\n'
    rustc -vV
    printf '\ncargo\n'
    cargo -V
    printf '\nrust_target_cfg_native\n'
    rustc --print cfg -C target-cpu=native
    printf '\nrust_target_features\n'
    rustc --print target-features
    printf '\nlscpu\n'
    lscpu
    printf '\nproc_cpu_model\n'
    rg -m 8 '^(model name|Hardware|Processor|CPU implementer|CPU part|vendor_id)' \
        /proc/cpuinfo || true
    printf '\nproc_status_affinity\n'
    rg '^(Cpus_allowed|Cpus_allowed_list|Mems_allowed|Mems_allowed_list):' \
        /proc/self/status
    printf '\ncgroup\n'
    cat /proc/self/cgroup

    printf '\nnetwork_interfaces\n'
    shopt -s nullglob
    for net_dir in /sys/class/net/*; do
        interface="${net_dir##*/}"
        printf 'interface=%s\n' "$interface"
        for field in \
            ifindex address mtu operstate carrier speed duplex tx_queue_len \
            gro_flush_timeout napi_defer_hard_irqs; do
            if [[ -r "$net_dir/$field" ]]; then
                printf '%s.%s=%s\n' "$interface" "$field" \
                    "$(< "$net_dir/$field")"
            else
                printf '%s.%s=unavailable\n' "$interface" "$field"
            fi
        done
        if [[ -r "$net_dir/device/numa_node" ]]; then
            printf '%s.device_numa_node=%s\n' "$interface" \
                "$(< "$net_dir/device/numa_node")"
        else
            printf '%s.device_numa_node=unavailable\n' "$interface"
        fi
        if [[ -r "$net_dir/device/local_cpulist" ]]; then
            printf '%s.device_local_cpulist=%s\n' "$interface" \
                "$(< "$net_dir/device/local_cpulist")"
        else
            printf '%s.device_local_cpulist=unavailable\n' "$interface"
        fi
        if [[ -e "$net_dir/device/driver" ]]; then
            driver_path="$(realpath -m -- "$net_dir/device/driver")"
            driver_name="${driver_path##*/}"
            printf '%s.driver=%s\n' "$interface" "$driver_name"
            if [[ -r "$net_dir/device/driver/module/version" ]]; then
                printf '%s.driver_module_version=%s\n' "$interface" \
                    "$(< "$net_dir/device/driver/module/version")"
            elif [[ -r "/sys/module/$driver_name/version" ]]; then
                printf '%s.driver_module_version=%s\n' "$interface" \
                    "$(< "/sys/module/$driver_name/version")"
            else
                printf '%s.driver_module_version=unavailable\n' "$interface"
            fi
        else
            printf '%s.driver=unavailable\n' "$interface"
            printf '%s.driver_module_version=unavailable\n' "$interface"
        fi
        for queue_dir in "$net_dir"/queues/rx-* "$net_dir"/queues/tx-*; do
            queue="${queue_dir##*/}"
            printf '%s.queue=%s\n' "$interface" "$queue"
            for control in rps_cpus rps_flow_cnt xps_cpus xps_rxqs; do
                if [[ -r "$queue_dir/$control" ]]; then
                    printf '%s.%s.%s=%s\n' "$interface" "$queue" "$control" \
                        "$(< "$queue_dir/$control")"
                fi
            done
        done
    done
    shopt -u nullglob

    printf '\nnetwork_ip_link\n'
    if command -v ip >/dev/null 2>&1; then
        printf 'ip_status=available\n'
        ip -details -statistics link show || true
        ip -details address show || true
        ip route show table all || true
    else
        printf 'ip_status=unavailable\n'
    fi

    printf '\nnetwork_ethtool\n'
    if command -v ethtool >/dev/null 2>&1; then
        printf 'ethtool_status=available\n'
        ethtool --version || true
        shopt -s nullglob
        for net_dir in /sys/class/net/*; do
            interface="${net_dir##*/}"
            printf 'ethtool_interface=%s\n' "$interface"
            ethtool "$interface" || true
            ethtool -k "$interface" || true
            ethtool -l "$interface" || true
            ethtool -g "$interface" || true
            ethtool -S "$interface" || true
        done
        shopt -u nullglob
    else
        printf 'ethtool_status=unavailable\n'
    fi

    printf '\nnetwork_sysctls\n'
    for sysctl_path in \
        /proc/sys/net/core/rmem_default \
        /proc/sys/net/core/rmem_max \
        /proc/sys/net/core/wmem_default \
        /proc/sys/net/core/wmem_max \
        /proc/sys/net/core/optmem_max \
        /proc/sys/net/core/netdev_max_backlog \
        /proc/sys/net/core/netdev_budget \
        /proc/sys/net/core/netdev_budget_usecs \
        /proc/sys/net/core/busy_read \
        /proc/sys/net/core/busy_poll \
        /proc/sys/net/core/rps_sock_flow_entries \
        /proc/sys/net/core/somaxconn \
        /proc/sys/net/ipv4/udp_mem \
        /proc/sys/net/ipv4/udp_rmem_min \
        /proc/sys/net/ipv4/udp_wmem_min \
        /proc/sys/net/ipv4/ip_local_port_range \
        /proc/sys/net/ipv4/tcp_max_syn_backlog \
        /proc/sys/net/ipv4/tcp_moderate_rcvbuf \
        /proc/sys/net/ipv4/tcp_rmem \
        /proc/sys/net/ipv4/tcp_wmem \
        /proc/sys/net/ipv4/tcp_syncookies; do
        sysctl_name="${sysctl_path#/proc/sys/}"
        if [[ -r "$sysctl_path" ]]; then
            printf '%s=%s\n' "$sysctl_name" "$(< "$sysctl_path")"
        else
            printf '%s=unavailable\n' "$sysctl_name"
        fi
    done

    printf '\nnetwork_steering\n'
    if [[ -r /proc/irq/default_smp_affinity ]]; then
        printf 'default_irq_smp_affinity=%s\n' \
            "$(< /proc/irq/default_smp_affinity)"
    else
        printf 'default_irq_smp_affinity=unavailable\n'
    fi
    printf 'relevant_interrupts\n'
    rg -n 'NET_RX|NET_TX|ena|eth|ens|enp|virtio|mlx|loopback' \
        /proc/interrupts || true
    printf '\nproc_softirqs\n'
    cat /proc/softirqs
    printf '\nproc_net_softnet_stat\n'
    cat /proc/net/softnet_stat
    printf '\nproc_net_dev\n'
    cat /proc/net/dev
    printf '\nproc_net_udp\n'
    cat /proc/net/udp
} >"$output_dir/host.txt" 2>&1

{
    printf 'source_commit=%s\nsource_tree=%s\n' "$source_commit" "$source_tree"
    printf 'source_archive_scope=Cargo.toml Cargo.lock %s\n' "$topic_rel"
    printf 'source_archive_sha256=%s\n' \
        "$(awk '{print $1}' "$output_dir/source-archive.sha256")"
    (
        cd "$repo_root" && sha256sum \
            "$experiment_rel/udp_batch.c" \
            "$experiment_rel/run_processes.py" \
            "$experiment_rel/validate_receipts.py" \
            "$experiment_rel/run_host.sh"
    )
} >"$output_dir/source-identity.txt"

gates_dir="$output_dir/gates"
mkdir -p -- "$gates_dir"
pinned_toolchain="$(sed -n 's/^channel *= *"\(.*\)"$/\1/p' \
    "$repo_root/rust-toolchain.toml")"
resolved_rustc="$(cd "$repo_root" && rustc --version)"
if [[ -z "$pinned_toolchain" \
    || "$resolved_rustc" != "rustc $pinned_toolchain "* ]]; then
    printf 'resolved "%s" does not match the pinned toolchain "%s"\n' \
        "$resolved_rustc" "$pinned_toolchain" >&2
    exit 2
fi
(cd "$repo_root" && git diff --check) >"$gates_dir/git-diff-check.log" 2>&1
(cd "$repo_root" && cargo fmt --all -- --check) \
    >"$gates_dir/cargo-fmt.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --lib --examples) \
    >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --doc) \
    >"$gates_dir/cargo-test-doc.log" 2>&1
(cd "$repo_root" \
    && cargo clippy --locked --workspace --all-targets -- -D warnings) \
    >"$gates_dir/cargo-clippy.log" 2>&1
(cd "$repo_root" && cargo bench --locked --workspace --no-run) \
    >"$gates_dir/cargo-bench-no-run.log" 2>&1
(cd "$repo_root" \
    && RUSTDOCFLAGS='-D warnings' cargo doc --locked --workspace --no-deps) \
    >"$gates_dir/cargo-doc.log" 2>&1
(
    cd "$repo_root"
    PYTHONPYCACHEPREFIX="$scratch_dir/pycache" python3 -m py_compile \
        "$experiment_rel/run_processes.py" \
        "$experiment_rel/validate_receipts.py"
    bash -n "$experiment_rel/run_host.sh"
) >"$gates_dir/script-syntax.log" 2>&1

build_flags=(
    -O3 -std=c11 -Wall -Wextra -Werror -Wpedantic
    -D_GNU_SOURCE -fno-lto -fno-omit-frame-pointer -pthread
)
{
    printf 'compiler=cc\n'
    printf 'flags='
    printf '%q ' "${build_flags[@]}"
    printf '\n'
} >"$output_dir/build-flags.txt"

binary="$scratch_dir/udp-batch"
cc "${build_flags[@]}" "$experiment_dir/udp_batch.c" -o "$binary" \
    >"$output_dir/native-build.log" 2>&1
(cd "$scratch_dir" && sha256sum udp-batch) >"$output_dir/binary.sha256"
readelf -hSWs "$binary" >"$output_dir/binary.readelf.txt"
nm -an "$binary" >"$output_dir/binary.symbols.txt"
objdump -drwC "$binary" >"$output_dir/codegen.txt"
objdump -drwC --disassemble=topic26_send_scalar_batch "$binary" \
    >"$output_dir/codegen-scalar.txt"
objdump -drwC --disassemble=topic26_send_mmsg_batch "$binary" \
    >"$output_dir/codegen-sendmmsg.txt"
objdump -drwC --disassemble=topic26_send_gso_batch "$binary" \
    >"$output_dir/codegen-udp-segment.txt"
rg -q '<topic26_send_scalar_batch>:' "$output_dir/codegen-scalar.txt"
rg -q '<topic26_send_mmsg_batch>:' "$output_dir/codegen-sendmmsg.txt"
rg -q '<topic26_send_gso_batch>:' "$output_dir/codegen-udp-segment.txt"
rg -n \
    'topic26_send_scalar_batch|topic26_send_mmsg_batch|topic26_send_gso_batch' \
    "$output_dir/codegen.txt" >"$output_dir/codegen-hook-search.txt"
gzip -n -9 "$output_dir/codegen.txt"

{
    timeout --signal=TERM --kill-after=5s 30s "$binary" scalar 2 0
    timeout --signal=TERM --kill-after=5s 30s "$binary" sendmmsg 2 0
    timeout --signal=TERM --kill-after=5s 30s "$binary" udp_segment 2 0
    timeout --signal=TERM --kill-after=5s 30s "$binary" udp_segment 2 0 --gro
} >"$output_dir/control-smoke.jsonl" 2>"$output_dir/control-smoke.stderr"
test ! -s "$output_dir/control-smoke.stderr"

python3 "$experiment_dir/run_processes.py" \
    --binary "$binary" \
    --output-dir "$output_dir/experiment" \
    >"$output_dir/process.log" 2>&1

python3 "$experiment_dir/validate_receipts.py" \
    --evidence-dir "$output_dir" \
    --source-root "$repo_root" \
    --allow-unsealed \
    >"$output_dir/validation.log" 2>&1

printf 'source_commit=%s\noutput=%s\n' "$source_commit" "$output_dir"
