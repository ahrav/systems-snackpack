#!/usr/bin/env bash
set -euo pipefail

if (($# < 3 || $# > 5)); then
    printf 'usage: %s BINARY RAW.csv SUMMARY.csv [BLOCKS] [CPU]\n' "$0" >&2
    exit 2
fi

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
binary="$1"
results="$2"
summary="$3"
blocks="${4:-12}"
cpu="${5:-0}"
cpu_was_requested=$(($# >= 5))

if [[ ! -x "$binary" ]]; then
    printf 'binary is not executable: %s\n' "$binary" >&2
    exit 2
fi
if ! [[ "$blocks" =~ ^[1-9][0-9]*$ ]]; then
    printf 'blocks must be a positive integer\n' >&2
    exit 2
fi
if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]]; then
    printf 'cpu must be a non-negative integer\n' >&2
    exit 2
fi

# The kernel reports the CPUs this process may run on; an empty result means the
# mask could not be read, in which case the probe below is the only gate.
cpus_allowed() {
    awk '/^Cpus_allowed_list:/ {print $2; exit}' /proc/self/status 2>/dev/null
}

# A single entry and a range both reduce to a low/high pair, so "6" and "4-5"
# take the same comparison.
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

# An installed taskset does not make the requested CPU usable: a cgroup cpuset
# or an inherited affinity mask can exclude it, and sched_setaffinity then fails
# on the first launch, leaving a truncated raw file and no summary. Resolve the
# CPU and prove it works before any measurement runs. An explicitly requested
# CPU is never silently substituted, because pinning to a different CPU than the
# caller asked for would misattribute the run.
if command -v taskset >/dev/null 2>&1; then
    if ! cpu_is_allowed "$cpu"; then
        if ((cpu_was_requested)); then
            printf 'cpu %s is outside the allowed cpu set (%s)\n' \
                "$cpu" "$(cpus_allowed)" >&2
            exit 2
        fi
        cpu="$(first_allowed_cpu)"
    fi
    if ! taskset -c "$cpu" true >/dev/null 2>&1; then
        printf 'taskset cannot pin to cpu %s (allowed cpu set: %s)\n' \
            "$cpu" "$(cpus_allowed)" >&2
        exit 2
    fi
    affinity="taskset -c $cpu"
else
    affinity="none"
fi

run_binary() {
    local order="$1"
    if [[ "$affinity" != "none" ]]; then
        taskset -c "$cpu" "$binary" "$order"
    else
        "$binary" "$order"
    fi
}

expected="pid,order,position,label,elapsed_ns,checksum,target_bytes,thrash_bytes"
printf 'block,launch,run,%s\n' "$expected" >"$results"

run=0
for ((block = 1; block <= blocks; block++)); do
    if ((block % 2 == 1)); then
        orders=(AB BA)
    else
        orders=(BA AB)
    fi

    for index in "${!orders[@]}"; do
        launch=$((index + 1))
        run=$((run + 1))
        output="$(run_binary "${orders[$index]}")"
        header="${output%%$'\n'*}"
        if [[ "$header" != "$expected" ]]; then
            printf 'unexpected output header: %s\n' "$header" >&2
            exit 1
        fi

        while IFS= read -r row; do
            printf '%d,%d,%d,%s\n' "$block" "$launch" "$run" "$row" >>"$results"
        done < <(printf '%s\n' "$output" | sed '1d')
    done
done

expected_lines=$((blocks * 4 + 1))
if [[ "$(wc -l <"$results")" -ne "$expected_lines" ]]; then
    printf 'expected %d lines in %s\n' "$expected_lines" "$results" >&2
    exit 1
fi

python3 "$script_dir/summarize.py" "$results" "$summary"
printf 'affinity=%s\nraw=%s\nsummary=%s\n' "$affinity" "$results" "$summary"
cat "$summary"
