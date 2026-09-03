#!/usr/bin/env bash
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
usage:
  run_host.sh prepare RECEIPT LABEL EXPECTED_HOST EXPECTED_ARCH SOURCE_COMMIT ARCHIVE_SHA256 ARCHIVE_PATH
  run_host.sh snapshot RECEIPT NAME PEER_IPV4
  run_host.sh seal RECEIPT
EOF
}

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

hex_length() {
    local value=$1
    local length=$2
    [[ ${#value} -eq $length && $value != *[!0-9a-f]* ]]
}

absolute_safe_path() {
    local value=$1
    [[ $value == /* && $value != *$'\n'* && $value != *$'\r'* ]]
}

require_linux() {
    [[ $(uname -s) == Linux ]] || fail 'Topic 55 host receipts require Linux'
}

write_steering_state() {
    local destination=$1
    {
        printf 'rps_sock_flow_entries='
        if [[ -r /proc/sys/net/core/rps_sock_flow_entries ]]; then
            cat /proc/sys/net/core/rps_sock_flow_entries
        else
            printf 'unavailable\n'
        fi
        find /sys/class/net/*/queues -maxdepth 2 \
            \( -name rps_cpus -o -name rps_flow_cnt -o \
            -name xps_cpus -o -name xps_rxqs \) -print 2>/dev/null | \
            LC_ALL=C sort | \
            while IFS= read -r path; do
                printf '%s=' "$path"
                cat "$path" 2>/dev/null || printf 'unreadable\n'
            done
    } >"$destination"
}

write_irq_affinity() {
    local destination=$1
    {
        local irq_path
        for irq_path in /proc/irq/[0-9]*; do
            [[ -d $irq_path ]] || continue
            local irq=${irq_path##*/}
            printf 'irq=%s smp_affinity=' "$irq"
            cat "$irq_path/smp_affinity" 2>/dev/null || printf 'unavailable\n'
            printf 'irq=%s smp_affinity_list=' "$irq"
            cat "$irq_path/smp_affinity_list" 2>/dev/null || printf 'unavailable\n'
        done
    } >"$destination"
}

prepare() {
    (($# == 7)) || { usage; exit 2; }
    local receipt=$1
    local label=$2
    local expected_host=$3
    local expected_arch=$4
    local source_commit=$5
    local archive_sha256=$6
    local archive_path=$7

    require_linux
    absolute_safe_path "$receipt" || fail 'receipt must be an absolute path'
    [[ ! -e $receipt ]] || fail 'receipt path must not already exist'
    absolute_safe_path "$archive_path" || fail 'archive path must be absolute'
    [[ -f $archive_path ]] || fail 'source archive is missing'
    hex_length "$source_commit" 40 || fail 'source commit must be 40 lowercase hexadecimal characters'
    hex_length "$archive_sha256" 64 || fail 'archive SHA-256 must be 64 lowercase hexadecimal characters'
    [[ $expected_arch == aarch64 || $expected_arch == x86_64 ]] || \
        fail 'expected architecture must be aarch64 or x86_64'

    local required=(
        awk bash cat chmod cmp cp dirname file find grep hostname ip lscpu
        mkdir mktemp mv nm nproc objdump python3 readelf readlink rg rm rustc
        rustdoc sed sha256sum sort tar uname xargs
    )
    local command_name
    for command_name in "${required[@]}"; do
        command -v "$command_name" >/dev/null 2>&1 || \
            fail "required command is missing: $command_name"
    done

    local runtime_host
    local runtime_arch
    runtime_host=$(hostname -f)
    runtime_arch=$(uname -m)
    [[ $runtime_host == "$expected_host" ]] || \
        fail "runtime hostname differs: expected=$expected_host actual=$runtime_host"
    [[ $runtime_arch == "$expected_arch" ]] || \
        fail "runtime architecture differs: expected=$expected_arch actual=$runtime_arch"

    local actual_archive_sha256
    actual_archive_sha256=$(sha256sum -- "$archive_path" | awk '{print $1}')
    [[ $actual_archive_sha256 == "$archive_sha256" ]] || \
        fail 'source archive SHA-256 differs'

    local source_prefix="systems-snackpack-${source_commit}/"
    local topic_prefix='topics/055-packet-steering-interrupts/'
    python3 -I -B - "$archive_path" "$source_prefix" "$topic_prefix" <<'PY'
import pathlib
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
source_prefix = sys.argv[2]
source_root = source_prefix.rstrip("/")
topic_prefix = source_prefix + sys.argv[3]
required = {
    topic_prefix + "Cargo.toml",
    topic_prefix + "src/lib.rs",
    topic_prefix + "examples/steering_costs.rs",
    topic_prefix + "experiment/udp_steering_probe.rs",
    topic_prefix + "experiment/run_host.sh",
    topic_prefix + "experiment/run_cross_host.sh",
    topic_prefix + "experiment/validate_receipt.py",
}
observed = set()
with tarfile.open(archive, "r:gz") as source:
    for member in source.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe archive path: {member.name}")
        parent_directories = {
            source_root,
            source_prefix + "topics",
            topic_prefix.rstrip("/"),
        }
        if member.name in parent_directories:
            if not member.isdir():
                raise SystemExit(f"archive parent is not a directory: {member.name}")
        elif not member.name.startswith(topic_prefix):
            raise SystemExit(f"archive member escapes topic prefix: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise SystemExit(f"archive contains a non-file member: {member.name}")
        observed.add(member.name)
missing = sorted(required - observed)
if missing:
    raise SystemExit("archive lacks required files: " + ", ".join(missing))
PY

    local source_work
    source_work=$(mktemp -d /tmp/topic55-source.XXXXXXXX)
    trap 'rm -rf -- "$source_work"' RETURN
    tar -xzf "$archive_path" --no-same-owner -C "$source_work"
    local archive_root="$source_work/${source_prefix%/}"
    local topic_dir="$archive_root/${topic_prefix%/}"
    local archived_runner="$topic_dir/experiment/run_host.sh"
    local external_runner
    external_runner=$(readlink -f -- "$0")
    cmp -- "$external_runner" "$archived_runner" >/dev/null || \
        fail 'external runner differs from the archived runner'

    mkdir -m 0700 -- "$receipt"
    mkdir -m 0700 -- "$receipt/source" "$receipt/host" "$receipt/build" \
        "$receipt/bin" "$receipt/snapshots" "$receipt/campaign"
    cp -- "$archive_path" "$receipt/source/source.tar.gz"
    cp -- "$topic_dir/experiment/udp_steering_probe.rs" "$receipt/source/udp_steering_probe.rs"
    printf '%s  source.tar.gz\n' "$archive_sha256" >"$receipt/source/source-archive.sha256"
    printf 'match\n' >"$receipt/source/run-host-match.txt"

    (
        cd "$archive_root"
        while IFS= read -r path; do
            sha256sum -- "$path"
        done < <(rg --files --hidden --no-ignore "$topic_prefix" | LC_ALL=C sort)
    ) >"$receipt/source/source-files.sha256"

    local probe_source="$topic_dir/experiment/udp_steering_probe.rs"
    local source_sha256
    source_sha256=$(sha256sum -- "$probe_source" | awk '{print $1}')
    local rust_flags=(
        --edition 2024 -D warnings -C opt-level=3 -C debuginfo=1
        -C target-cpu=generic -C overflow-checks=yes
    )
    rustc "${rust_flags[@]}" "$probe_source" -o "$receipt/bin/udp_steering_probe" \
        >"$receipt/build/probe-compile.stdout" 2>"$receipt/build/probe-compile.stderr"
    rustc --edition 2024 --test -D warnings "$topic_dir/src/lib.rs" \
        -o "$receipt/bin/model_tests" \
        >"$receipt/build/model-test-compile.stdout" 2>"$receipt/build/model-test-compile.stderr"
    "$receipt/bin/model_tests" >"$receipt/build/model-tests.txt"
    rustc --edition 2024 --crate-name packet_steering_interrupts --crate-type lib \
        -D warnings "$topic_dir/src/lib.rs" -o "$receipt/build/libpacket_steering_interrupts.rlib"
    rustdoc --edition 2024 --test "$topic_dir/src/lib.rs" \
        --crate-name packet_steering_interrupts \
        --extern packet_steering_interrupts="$receipt/build/libpacket_steering_interrupts.rlib" \
        >"$receipt/build/doctests.txt"
    rustc --edition 2024 -D warnings "$topic_dir/examples/steering_costs.rs" \
        --extern packet_steering_interrupts="$receipt/build/libpacket_steering_interrupts.rlib" \
        -o "$receipt/bin/steering_costs"
    "$receipt/bin/steering_costs" >"$receipt/build/steering-costs.txt"

    rustc --version --verbose >"$receipt/host/rustc.txt"
    uname -a >"$receipt/host/uname.txt"
    lscpu >"$receipt/host/lscpu.txt"
    nproc >"$receipt/host/nproc.txt"
    ip -details link show >"$receipt/host/ip-link.txt"
    ip -4 address show >"$receipt/host/ip-address.txt"
    cp -- /proc/interrupts "$receipt/host/interrupts.prepare.txt"
    cp -- /proc/net/softnet_stat "$receipt/host/softnet.prepare.txt"
    awk 'NR == 1 {print "columns=" NF; exit}' /proc/net/softnet_stat \
        >"$receipt/host/softnet-format.txt"
    find /sys/class/net/*/queues -mindepth 1 -maxdepth 1 -type d -print | \
        LC_ALL=C sort >"$receipt/host/queues.txt"
    write_steering_state "$receipt/host/steering.prepare.txt"
    write_irq_affinity "$receipt/host/irq-affinity.prepare.txt"
    {
        for network_path in /sys/class/net/*; do
            interface=${network_path##*/}
            printf 'interface=%s\n' "$interface"
            printf 'driver_path=%s\n' "$(readlink -f -- "$network_path/device/driver" 2>/dev/null || printf unavailable)"
            printf 'module_path=%s\n' "$(readlink -f -- "$network_path/device/driver/module" 2>/dev/null || printf unavailable)"
            printf 'module_version='
            cat "$network_path/device/driver/module/version" 2>/dev/null || printf 'unavailable\n'
        done
    } >"$receipt/host/net-drivers.txt"
    if command -v ethtool >/dev/null 2>&1; then
        {
            printf 'ethtool=available\n'
            for network_path in /sys/class/net/*; do
                interface=${network_path##*/}
                [[ $interface == lo ]] && continue
                printf 'interface=%s\n' "$interface"
                ethtool -i "$interface" 2>&1 || true
                ethtool -l "$interface" 2>&1 || true
                ethtool -x "$interface" 2>&1 || true
                for flow_kind in tcp4 udp4 tcp6 udp6; do
                    printf 'rx_flow_hash=%s\n' "$flow_kind"
                    ethtool -n "$interface" rx-flow-hash "$flow_kind" 2>&1 || true
                done
            done
        } >"$receipt/host/ethtool.txt"
    else
        printf 'ethtool=unavailable\n' >"$receipt/host/ethtool.txt"
    fi
    file "$receipt/bin/udp_steering_probe" >"$receipt/build/probe-file.txt"
    readelf -hW "$receipt/bin/udp_steering_probe" >"$receipt/build/probe-elf-header.txt"
    readelf -Ws "$receipt/bin/udp_steering_probe" >"$receipt/build/probe-symbols.txt"
    nm -u "$receipt/bin/udp_steering_probe" >"$receipt/build/probe-undefined-symbols.txt"
    objdump -d "$receipt/bin/udp_steering_probe" | \
        rg -n -C 4 'getsockopt' >"$receipt/build/probe-getsockopt-disassembly.txt"

    local binary_sha256
    local runner_sha256
    binary_sha256=$(sha256sum -- "$receipt/bin/udp_steering_probe" | awk '{print $1}')
    runner_sha256=$(sha256sum -- "$external_runner" | awk '{print $1}')
    {
        printf 'schema=topic55-provenance.v1\n'
        printf 'target_label=%s\n' "$label"
        printf 'expected_hostname=%s\n' "$expected_host"
        printf 'runtime_hostname=%s\n' "$runtime_host"
        printf 'expected_architecture=%s\n' "$expected_arch"
        printf 'runtime_architecture=%s\n' "$runtime_arch"
        printf 'source_commit=%s\n' "$source_commit"
        printf 'source_archive_sha256=%s\n' "$archive_sha256"
        printf 'probe_source_sha256=%s\n' "$source_sha256"
        printf 'probe_binary_sha256=%s\n' "$binary_sha256"
        printf 'runner_sha256=%s\n' "$runner_sha256"
        printf 'source_prefix=%s\n' "$source_prefix"
        printf 'topic_prefix=%s\n' "$topic_prefix"
        printf 'compile_flags=%s\n' "${rust_flags[*]}"
        printf 'timing_claim=false\n'
    } >"$receipt/provenance.txt"
    printf 'prepared\n' >"$receipt/STATE"
    printf 'PREPARE_OK receipt=%s source_sha256=%s binary_sha256=%s\n' \
        "$receipt" "$source_sha256" "$binary_sha256"
}

snapshot() {
    (($# == 3)) || { usage; exit 2; }
    local receipt=$1
    local name=$2
    local peer=$3
    require_linux
    absolute_safe_path "$receipt" || fail 'receipt must be an absolute path'
    [[ -d $receipt && $(cat "$receipt/STATE" 2>/dev/null) == prepared ]] || \
        fail 'receipt is not prepared'
    [[ $name != *[!A-Za-z0-9_.-]* && -n $name ]] || fail 'snapshot name is invalid'
    [[ $peer != *[!0-9.]* && -n $peer ]] || fail 'peer IPv4 is invalid'

    local route="$receipt/snapshots/${name}.route.txt"
    ip -4 route get "$peer" >"$route"
    local interface
    interface=$(awk '{for (index = 1; index <= NF; index++) if ($index == "dev") {print $(index + 1); exit}}' "$route")
    [[ -n $interface && $interface != lo ]] || fail 'tested route must not use loopback'
    ip -s link show dev "$interface" >"$receipt/snapshots/${name}.link.txt"
    cp -- /proc/interrupts "$receipt/snapshots/${name}.interrupts.txt"
    cp -- /proc/net/softnet_stat "$receipt/snapshots/${name}.softnet.txt"
    write_steering_state "$receipt/snapshots/${name}.steering.txt"
    printf 'SNAPSHOT_OK name=%s peer=%s interface=%s\n' "$name" "$peer" "$interface"
}

seal() {
    (($# == 1)) || { usage; exit 2; }
    local receipt=$1
    require_linux
    absolute_safe_path "$receipt" || fail 'receipt must be an absolute path'
    [[ -d $receipt && $(cat "$receipt/STATE" 2>/dev/null) == prepared ]] || \
        fail 'receipt is not prepared'
    [[ ! -e $receipt/SEALED && ! -e $receipt/MANIFEST.sha256 ]] || \
        fail 'receipt is already sealed'
    [[ -f $receipt/campaign/plan.tsv ]] || fail 'campaign plan is missing'

    local source_sha256
    source_sha256=$(awk -F= '$1 == "probe_source_sha256" {print $2}' "$receipt/provenance.txt")
    hex_length "$source_sha256" 64 || fail 'provenance lacks a valid probe source SHA-256'
    local output_count
    output_count=$(find "$receipt/campaign" -type f -name '*.out' | wc -l | awk '{print $1}')
    [[ $output_count -eq 48 ]] || fail "expected 48 probe outputs, found $output_count"
    local output
    while IFS= read -r output; do
        [[ $(grep -c '^summary status=ok ' "$output") -eq 1 ]] || \
            fail "probe output lacks one successful summary: $output"
        local summary
        local flows
        summary=$(grep '^summary status=ok ' "$output")
        flows=$(sed -n 's/.* flows=\([0-9][0-9]*\) .*/\1/p' <<<"$summary")
        [[ $flows == 1 || $flows == 128 ]] || fail "wrong flow count: $output"
        [[ $summary == *" observations=256 "* ]] || fail "wrong observation count: $output"
        [[ $summary == *" peer_stable=$flows/$flows "* ]] || fail "peer instability: $output"
        [[ $summary == *" source_sha256=$source_sha256" ]] || fail "wrong source hash: $output"
        if [[ $summary == *' role=client '* ]]; then
            [[ $summary == *" cpu_stable=$flows/$flows "* ]] || fail "CPU instability: $output"
            [[ $summary == *" napi_stable=$flows/$flows "* ]] || fail "NAPI instability: $output"
            [[ $summary == *" pair_stable=$flows/$flows "* ]] || fail "CPU/NAPI pair instability: $output"
            [[ $summary == *" known_cpu_flows=$flows/$flows "* ]] || fail "unknown client CPU: $output"
            [[ $summary == *" positive_napi_flows=$flows/$flows "* ]] || fail "unknown client NAPI ID: $output"
        elif [[ $summary != *' role=server placement_scope=shared_socket_only '* ]]; then
            fail "unknown probe role or placement scope: $output"
        fi
    done < <(find "$receipt/campaign" -type f -name '*.out' | LC_ALL=C sort)

    cp -- /proc/interrupts "$receipt/host/interrupts.seal.txt"
    cp -- /proc/net/softnet_stat "$receipt/host/softnet.seal.txt"
    write_steering_state "$receipt/host/steering.seal.txt"
    write_irq_affinity "$receipt/host/irq-affinity.seal.txt"
    printf 'sealed\n' >"$receipt/STATE"
    printf 'source-bound correctness and placement receipt; no timing claim\n' >"$receipt/SEALED"
    local manifest_temporary
    manifest_temporary=$(mktemp /tmp/topic55-manifest.XXXXXXXX)
    (
        cd "$receipt"
        find . -type f ! -name MANIFEST.sha256 -print0 | LC_ALL=C sort -z | \
            xargs -0 sha256sum
    ) >"$manifest_temporary"
    mv -- "$manifest_temporary" "$receipt/MANIFEST.sha256"
    local manifest_sha256
    local files
    manifest_sha256=$(sha256sum -- "$receipt/MANIFEST.sha256" | awk '{print $1}')
    files=$(wc -l <"$receipt/MANIFEST.sha256" | awk '{print $1}')
    chmod -R a-w -- "$receipt"
    printf 'SEAL_OK receipt=%s files=%s manifest_sha256=%s\n' \
        "$receipt" "$files" "$manifest_sha256"
}

if (($# == 0)); then
    usage
    exit 2
fi

operation=$1
shift
case $operation in
    prepare) prepare "$@" ;;
    snapshot) snapshot "$@" ;;
    seal) seal "$@" ;;
    *) usage; exit 2 ;;
esac
