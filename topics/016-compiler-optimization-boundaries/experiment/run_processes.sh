#!/usr/bin/env bash
set -euo pipefail

if (($# < 3 || $# > 4)); then
    printf 'usage: %s BINARY RAW.csv SUMMARY.csv [CPU]\n' "$0" >&2
    exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
binary="$1"
raw_path="$2"
summary_path="$3"
pairs=12

if [[ ! -x "$binary" ]]; then
    printf 'binary is not executable: %s\n' "$binary" >&2
    exit 2
fi

cpus_allowed() {
    awk '/^Cpus_allowed_list:/ {print $2; exit}' /proc/self/status 2>/dev/null
}

cpu_is_allowed() {
    local want="$1" spec entry
    spec="$(cpus_allowed)"
    [[ -n "$spec" ]] || return 0
    local IFS=,
    for entry in $spec; do
        if ((want >= ${entry%%-*} && want <= ${entry##*-})); then
            return 0
        fi
    done
    return 1
}

first_allowed_cpu() {
    local entry
    entry="$(cpus_allowed)"
    entry="${entry%%,*}"
    printf '%s' "${entry%%-*}"
}

if (($# == 4)); then
    cpu="$4"
    if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]]; then
        printf 'CPU must be a non-negative integer\n' >&2
        exit 2
    fi
    cpu_was_requested=1
else
    cpu=0
    cpu_was_requested=0
fi

if command -v taskset >/dev/null 2>&1; then
    if ! cpu_is_allowed "$cpu"; then
        if ((cpu_was_requested)); then
            printf 'CPU %s is outside the allowed CPU set (%s)\n' \
                "$cpu" "$(cpus_allowed)" >&2
            exit 2
        fi
        cpu="$(first_allowed_cpu)"
    fi
    if [[ -z "$cpu" ]] || ! taskset -c "$cpu" true >/dev/null 2>&1; then
        printf 'taskset cannot pin to CPU %s (allowed CPU set: %s)\n' \
            "${cpu:-unknown}" "$(cpus_allowed)" >&2
        exit 2
    fi
    affinity="taskset -c $cpu"
else
    if ((cpu_was_requested)); then
        printf 'CPU pinning was requested but taskset is unavailable\n' >&2
        exit 2
    fi
    affinity="none"
fi

# The Python parent starts one binary process and measures from immediately
# before spawn through wait. Python startup remains outside `process_ns`.
measure_process() {
    local mode="$1" measured
    local -a command
    command=(python3 - "$binary" "$mode")
    if [[ "$affinity" != "none" ]]; then
        command=(taskset -c "$cpu" "${command[@]}")
    fi

    if ! measured="$("${command[@]}" <<'PY'
import subprocess
import os
import sys
import time

binary, mode = sys.argv[1:]
arguments = [binary, mode]
elements = os.environ.get("TOPIC16_ELEMENTS")
rounds = os.environ.get("TOPIC16_ROUNDS")
if rounds is not None and elements is None:
    raise SystemExit("TOPIC16_ROUNDS requires TOPIC16_ELEMENTS")
if elements is not None:
    arguments.append(elements)
if rounds is not None:
    arguments.append(rounds)
start = time.monotonic_ns()
completed = subprocess.run(
    arguments,
    check=False,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
elapsed_ns = time.monotonic_ns() - start
if completed.returncode != 0:
    sys.stderr.write(completed.stderr)
    raise SystemExit(
        f"{mode}: benchmark process exited with status {completed.returncode}"
    )
if completed.stderr:
    sys.stderr.write(completed.stderr)
    raise SystemExit(f"{mode}: benchmark process wrote to stderr")
payload = completed.stdout.strip()
if not payload or "\n" in payload:
    raise SystemExit(f"{mode}: expected exactly one non-empty stdout line")
print(f"{elapsed_ns}\t{payload}")
PY
    )"; then
        return 1
    fi
    printf '%s\n' "$measured"
}

parse_payload() {
    local expected_mode="$1" payload="$2" token key value
    local seen_mode=0
    local seen_elements=0
    local seen_rounds=0
    local seen_checksum=0
    local seen_steady_ns=0
    parsed_mode=
    parsed_elements=
    parsed_rounds=
    parsed_checksum=
    parsed_steady_ns=

    for token in $payload; do
        if [[ ! "$token" =~ ^([a-z_]+)=([A-Za-z0-9_-]+)$ ]]; then
            printf '%s: malformed output token: %s\n' "$expected_mode" "$token" >&2
            return 1
        fi
        key="${BASH_REMATCH[1]}"
        value="${BASH_REMATCH[2]}"
        case "$key" in
            mode)
                if ((seen_mode)); then
                    printf '%s: duplicate output key: %s\n' "$expected_mode" "$key" >&2
                    return 1
                fi
                seen_mode=1
                parsed_mode="$value"
                ;;
            elements)
                if ((seen_elements)); then
                    printf '%s: duplicate output key: %s\n' "$expected_mode" "$key" >&2
                    return 1
                fi
                seen_elements=1
                parsed_elements="$value"
                ;;
            rounds)
                if ((seen_rounds)); then
                    printf '%s: duplicate output key: %s\n' "$expected_mode" "$key" >&2
                    return 1
                fi
                seen_rounds=1
                parsed_rounds="$value"
                ;;
            checksum)
                if ((seen_checksum)); then
                    printf '%s: duplicate output key: %s\n' "$expected_mode" "$key" >&2
                    return 1
                fi
                seen_checksum=1
                parsed_checksum="$value"
                ;;
            steady_ns)
                if ((seen_steady_ns)); then
                    printf '%s: duplicate output key: %s\n' "$expected_mode" "$key" >&2
                    return 1
                fi
                seen_steady_ns=1
                parsed_steady_ns="$value"
                ;;
            *)
                printf '%s: unexpected output key: %s\n' "$expected_mode" "$key" >&2
                return 1
                ;;
        esac
    done

    if [[ "$parsed_mode" != "$expected_mode" ]]; then
        printf 'requested mode %s, process reported %s\n' \
            "$expected_mode" "${parsed_mode:-<missing>}" >&2
        return 1
    fi
    for value in \
        "$parsed_elements" "$parsed_rounds" "$parsed_checksum" "$parsed_steady_ns"; do
        if ! [[ "$value" =~ ^[1-9][0-9]*$|^0$ ]]; then
            printf '%s: missing or non-integer output field\n' "$expected_mode" >&2
            return 1
        fi
    done
    if ((parsed_elements == 0 || parsed_rounds == 0 || parsed_steady_ns == 0)); then
        printf '%s: elements, rounds, and steady_ns must be positive\n' \
            "$expected_mode" >&2
        return 1
    fi
}

raw_dir="$(dirname -- "$raw_path")"
mkdir -p -- "$raw_dir" "$(dirname -- "$summary_path")"
raw_tmp="$(mktemp "$raw_dir/.topic16-raw.XXXXXX")"
cleanup() {
    rm -f -- "$raw_tmp"
}
trap cleanup EXIT

printf '%s\n' \
    'comparison,pair,order,position,mode,steady_ns,process_ns,elements,rounds,checksum' \
    >"$raw_tmp"

comparisons=("imported/local:imported:local" "opaque/local:opaque:local")
for specification in "${comparisons[@]}"; do
    IFS=: read -r comparison mode_a mode_b <<<"$specification"
    for ((pair = 1; pair <= pairs; pair++)); do
        if ((pair % 2 == 1)); then
            order=AB
            modes=("$mode_a" "$mode_b")
        else
            order=BA
            modes=("$mode_b" "$mode_a")
        fi

        for index in "${!modes[@]}"; do
            position=$((index + 1))
            mode="${modes[$index]}"
            measured="$(measure_process "$mode")"
            process_ns="${measured%%$'\t'*}"
            payload="${measured#*$'\t'}"
            if ! [[ "$process_ns" =~ ^[1-9][0-9]*$ ]]; then
                printf '%s: process_ns must be positive\n' "$mode" >&2
                exit 1
            fi
            parse_payload "$mode" "$payload"
            if ((process_ns <= parsed_steady_ns)); then
                printf '%s: process_ns must exceed steady_ns\n' "$mode" >&2
                exit 1
            fi
            printf '%s,%d,%s,%d,%s,%s,%s,%s,%s,%s\n' \
                "$comparison" "$pair" "$order" "$position" "$mode" \
                "$parsed_steady_ns" "$process_ns" "$parsed_elements" \
                "$parsed_rounds" "$parsed_checksum" >>"$raw_tmp"
        done
    done
done

expected_lines=$((2 * pairs * 2 + 1))
if [[ "$(wc -l <"$raw_tmp")" -ne "$expected_lines" ]]; then
    printf 'expected %d lines in the raw record\n' "$expected_lines" >&2
    exit 1
fi

mv -- "$raw_tmp" "$raw_path"
python3 "$script_dir/summarize.py" "$raw_path" "$summary_path"
printf 'affinity=%s\npairs_per_comparison=%d\nraw=%s\nsummary=%s\n' \
    "$affinity" "$pairs" "$raw_path" "$summary_path"
rg -n '^' "$summary_path"
