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

if [[ ! -x "$binary" ]]; then
    printf 'binary is not executable: %s\n' "$binary" >&2
    exit 2
fi
if ! [[ "$blocks" =~ ^[1-9][0-9]*$ ]]; then
    printf 'blocks must be a positive integer\n' >&2
    exit 2
fi

run_binary() {
    local order="$1"
    if command -v taskset >/dev/null 2>&1; then
        taskset -c "$cpu" "$binary" "$order"
    else
        "$binary" "$order"
    fi
}

printf '%s\n' \
    "block,launch,run,pid,order,position,label,elapsed_ns,checksum,target_bytes,thrash_bytes" \
    >"$results"

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
        expected="pid,order,position,label,elapsed_ns,checksum,target_bytes,thrash_bytes"
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
printf 'raw=%s\nsummary=%s\n' "$results" "$summary"
cat "$summary"
