#!/usr/bin/env bash
# shellcheck disable=SC2029
set -euo pipefail

usage() {
    cat >&2 <<'EOF'
usage: run_cross_host.sh ARM_HOST ARM_RUNNER ARM_RECEIPT ARM_IPV4 X86_HOST X86_RUNNER X86_RECEIPT X86_IPV4
EOF
}

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

if (($# != 8)); then
    usage
    exit 2
fi

arm_host=$1
arm_runner=$2
arm_receipt=$3
arm_ip=$4
x86_host=$5
x86_runner=$6
x86_receipt=$7
x86_ip=$8

for host in "$arm_host" "$x86_host"; do
    [[ $host == [A-Za-z0-9]* && $host != *[!A-Za-z0-9._-]* ]] || fail "unsafe host: $host"
done
for path in "$arm_runner" "$arm_receipt" "$x86_runner" "$x86_receipt"; do
    [[ $path == /* && $path != *[!A-Za-z0-9._/-]* ]] || fail "unsafe remote path: $path"
done
for address in "$arm_ip" "$x86_ip"; do
    [[ -n $address && $address != *[!0-9.]* ]] || fail "unsafe IPv4 address: $address"
done

arm_source_sha256=$(
    ssh "$arm_host" "awk -F= '\$1 == \"probe_source_sha256\" {print \$2}' '$arm_receipt/provenance.txt'"
)
x86_source_sha256=$(
    ssh "$x86_host" "awk -F= '\$1 == \"probe_source_sha256\" {print \$2}' '$x86_receipt/provenance.txt'"
)
[[ ${#arm_source_sha256} -eq 64 && $arm_source_sha256 != *[!0-9a-f]* ]] || \
    fail 'Arm receipt has no valid probe source SHA-256'
[[ $x86_source_sha256 == "$arm_source_sha256" ]] || fail 'host probe source hashes differ'
source_sha256=$arm_source_sha256

plan_rows=(
    $'campaign\t1\t1\tA\tone\t1\t256'
    $'campaign\t1\t2\tB\tmany\t128\t2'
    $'campaign\t1\t3\tB\tmany\t128\t2'
    $'campaign\t1\t4\tA\tone\t1\t256'
    $'campaign\t2\t1\tB\tmany\t128\t2'
    $'campaign\t2\t2\tA\tone\t1\t256'
    $'campaign\t2\t3\tA\tone\t1\t256'
    $'campaign\t2\t4\tB\tmany\t128\t2'
    $'campaign\t3\t1\tA\tone\t1\t256'
    $'campaign\t3\t2\tB\tmany\t128\t2'
    $'campaign\t3\t3\tB\tmany\t128\t2'
    $'campaign\t3\t4\tA\tone\t1\t256'
    $'campaign\t4\t1\tB\tmany\t128\t2'
    $'campaign\t4\t2\tA\tone\t1\t256'
    $'campaign\t4\t3\tA\tone\t1\t256'
    $'campaign\t4\t4\tB\tmany\t128\t2'
    $'control\t5\t1\tX\tmany\t128\t2'
    $'control\t5\t2\tY\tmany\t128\t2'
    $'control\t5\t3\tY\tmany\t128\t2'
    $'control\t5\t4\tX\tmany\t128\t2'
    $'control\t6\t1\tY\tmany\t128\t2'
    $'control\t6\t2\tX\tmany\t128\t2'
    $'control\t6\t3\tX\tmany\t128\t2'
    $'control\t6\t4\tY\tmany\t128\t2'
)

write_plan() {
    local host=$1
    local receipt=$2
    {
        printf 'scenario\tblock\tperiod\tlabel\ttreatment\tflows\tpackets_per_flow\n'
        printf '%s\n' "${plan_rows[@]}"
    } | ssh "$host" "umask 077; tee '$receipt/campaign/plan.tsv' >/dev/null"
}

write_plan "$arm_host" "$arm_receipt"
write_plan "$x86_host" "$x86_receipt"

ssh "$arm_host" "'$arm_runner' snapshot '$arm_receipt' before '$x86_ip'"
ssh "$x86_host" "'$x86_runner' snapshot '$x86_receipt' before '$arm_ip'"

# The remote probe holds its UDP port for up to a 30-second read timeout;
# killing it before reaping the SSH job keeps error reporting immediate.
stop_server_job() {
    local host=$1
    local receipt=$2
    local job=$3
    timeout 10 ssh -n "$host" "pkill -f -- '$receipt/bin/udp_steering_probe'" 2>/dev/null || true
    kill -- "$job" 2>/dev/null || true
    wait "$job" 2>/dev/null || true
}

run_direction() {
    local sequence=$1
    local stem=$2
    local flows=$3
    local packets_per_flow=$4
    local server_host=$5
    local server_receipt=$6
    local server_ip=$7
    local server_name=$8
    local client_host=$9
    local client_receipt=${10}
    local client_name=${11}
    local port=$((46000 + sequence))
    local server_job

    ssh -n "$server_host" \
        "'$server_receipt/bin/udp_steering_probe' server '$server_ip' '$port' '$flows' '$packets_per_flow' '$source_sha256' >'$server_receipt/campaign/$stem-$server_name.out' 2>'$server_receipt/campaign/$stem-$server_name.err'" &
    server_job=$!
    local ready=0
    for _ in {1..40}; do
        if ! kill -0 "$server_job" 2>/dev/null; then
            wait "$server_job" || true
            fail "server exited before readiness: $stem $server_name"
        fi
        if ssh "$server_host" \
            "grep -q '^ready role=server ' '$server_receipt/campaign/$stem-$server_name.out' 2>/dev/null"; then
            ready=1
            break
        fi
        sleep 0.25
    done
    if ((ready == 0)); then
        stop_server_job "$server_host" "$server_receipt" "$server_job"
        fail "server did not become ready: $stem $server_name"
    fi
    if ! ssh "$client_host" \
        "'$client_receipt/bin/udp_steering_probe' client '$server_ip' '$port' '$flows' '$packets_per_flow' '$source_sha256' >'$client_receipt/campaign/$stem-$client_name.out' 2>'$client_receipt/campaign/$stem-$client_name.err'"; then
        stop_server_job "$server_host" "$server_receipt" "$server_job"
        fail "client failed: $stem $client_name"
    fi
    wait "$server_job" || fail "server failed: $stem $server_name"
}

sequence=0
for row in "${plan_rows[@]}"; do
    IFS=$'\t' read -r scenario block period label treatment flows packets_per_flow <<<"$row"
    sequence=$((sequence + 1))
    stem=$(printf '%03d-%s-b%02d-p%d-%s-%s' \
        "$sequence" "$scenario" "$block" "$period" "$label" "$treatment")
    run_direction "$((sequence * 2))" "$stem" "$flows" "$packets_per_flow" \
        "$arm_host" "$arm_receipt" "$arm_ip" arm-server \
        "$x86_host" "$x86_receipt" x86-client
    run_direction "$((sequence * 2 + 1))" "$stem" "$flows" "$packets_per_flow" \
        "$x86_host" "$x86_receipt" "$x86_ip" x86-server \
        "$arm_host" "$arm_receipt" arm-client
    printf 'CASE_OK sequence=%s scenario=%s block=%s period=%s label=%s treatment=%s\n' \
        "$sequence" "$scenario" "$block" "$period" "$label" "$treatment"
done

ssh "$arm_host" "'$arm_runner' snapshot '$arm_receipt' after '$x86_ip'"
ssh "$x86_host" "'$x86_runner' snapshot '$x86_receipt' after '$arm_ip'"
ssh "$arm_host" "'$arm_runner' seal '$arm_receipt'"
ssh "$x86_host" "'$x86_runner' seal '$x86_receipt'"
printf 'CAMPAIGN_OK cases=%s directions_per_case=2 source_sha256=%s timing_claim=false\n' \
    "${#plan_rows[@]}" "$source_sha256"
