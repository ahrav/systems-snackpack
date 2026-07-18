#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
output_dir=${1:-/tmp/systems-snackpack-topic-007}
pairs=${PAIRS:-12}
length=${LENGTH:-262144}
repetitions=${REPETITIONS:-384}
warmup_repetitions=${WARMUP_REPETITIONS:-16}

for value_name in pairs length repetitions warmup_repetitions; do
  value=${!value_name}
  if [[ ! $value =~ ^(0|[1-9][0-9]*)$ ]]; then
    echo "$value_name must be an unsigned integer, got: $value" >&2
    exit 2
  fi
done
if (( pairs != 12 )); then
  echo "PAIRS must be 12 for the recorded order-statistic interval" >&2
  exit 2
fi
if (( length == 0 || repetitions == 0 || warmup_repetitions == 0 )); then
  echo "LENGTH, REPETITIONS, and WARMUP_REPETITIONS must be nonzero" >&2
  exit 2
fi
for command_name in cargo date dirname gcc hostname jq lscpu mkdir nproc python3 \
  rustc sed seq sha256sum tail taskset tee uname; do
  if ! command -v "$command_name" >/dev/null; then
    echo "required command not found: $command_name" >&2
    exit 2
  fi
done

mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
cd "$root"

allowed=$(taskset -pc $$ | sed 's/.*: //')
if [[ ! $allowed =~ ^([0-9]+) ]]; then
  echo "failed to parse the first allowed CPU from: $allowed" >&2
  exit 2
fi
cpu=${CPU:-${BASH_REMATCH[1]}}
if [[ ! $cpu =~ ^(0|[1-9][0-9]*)$ ]]; then
  echo "CPU must name one logical CPU, got: $cpu" >&2
  exit 2
fi

export CARGO_TARGET_DIR="$output_dir/target"
# Cargo prefers an inherited CARGO_ENCODED_RUSTFLAGS over RUSTFLAGS; clear it
# so the flags recorded in host-env.txt are the flags the build actually used.
unset CARGO_ENCODED_RUSTFLAGS
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C no-vectorize-loops -C no-vectorize-slp"
raw="$output_dir/processes.txt"
env_record="$output_dir/host-env.txt"

{
  printf 'captured_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'host=%s\n' "$(hostname -f 2>/dev/null || hostname)"
  printf 'cpu=%s\n' "$cpu"
  printf 'pairs=%s\n' "$pairs"
  printf 'length=%s\n' "$length"
  printf 'repetitions=%s\n' "$repetitions"
  printf 'warmup_repetitions=%s\n' "$warmup_repetitions"
  printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
  uname -a
  lscpu
  printf 'online_cpus=' && nproc
  printf 'allowed_cpus=' && taskset -pc $$
  rustc -Vv
  cargo -V
  gcc --version
  rustc -C target-cpu=native --print cfg
} > "$env_record"

bench_binary=$(
  cargo bench --message-format=json --quiet -p systems-snackpack-topic-007 \
    --bench control_flow --no-run \
    | jq -r 'select(.reason == "compiler-artifact"
        and .target.name == "control_flow"
        and (.target.kind | index("bench")))
        | .executable // empty' \
    | tail -n 1
)
if [[ -z "$bench_binary" || ! -x "$bench_binary" ]]; then
  echo "failed to locate the control_flow bench binary from Cargo JSON" >&2
  exit 1
fi

: > "$raw"
{
  printf 'SESSION_START utc=%s host=%s cpu=%s pairs=%s\n' \
    "$(date -u +%FT%TZ)" "$(hostname -f 2>/dev/null || hostname)" "$cpu" "$pairs"
  sha256sum \
    topics/007-branchless-predictable-control-flow/src/lib.rs \
    topics/007-branchless-predictable-control-flow/benches/control_flow.rs \
    "$bench_binary"
  taskset -c "$cpu" "$bench_binary" --verify
} | tee -a "$raw"

for pair in $(seq 1 "$pairs"); do
  # Shift the second six-pair cycle by one permutation. Each pattern order then
  # appears once with branch/select and once with select/branch ordering.
  pattern_order=$(( (pair - 1 + (pair - 1) / 6) % 6 ))
  case $pattern_order in
    0) patterns=(zeros alternating random) ;;
    1) patterns=(zeros random alternating) ;;
    2) patterns=(alternating zeros random) ;;
    3) patterns=(alternating random zeros) ;;
    4) patterns=(random zeros alternating) ;;
    5) patterns=(random alternating zeros) ;;
  esac
  if (( pair % 2 == 1 )); then
    variants=(branch select)
  else
    variants=(select branch)
  fi

  printf 'PAIR_START pair=%d pattern_order=%s,%s,%s variant_order=%s,%s utc=%s\n' \
    "$pair" "${patterns[0]}" "${patterns[1]}" "${patterns[2]}" \
    "${variants[0]}" "${variants[1]}" "$(date -u +%FT%TZ)" | tee -a "$raw"
  for pattern in "${patterns[@]}"; do
    for order in 0 1; do
      variant=${variants[$order]}
      external_start=$(date +%s%N)
      result=$(
        taskset -c "$cpu" "$bench_binary" \
          --variant "$variant" \
          --pattern "$pattern" \
          --length "$length" \
          --repetitions "$repetitions" \
          --warmup-repetitions "$warmup_repetitions" \
          --pair "$pair" \
          --order "$((order + 1))"
      )
      external_wall_ns=$(( $(date +%s%N) - external_start ))
      printf '%s external_wall_ns=%d cpu=%d\n' "$result" "$external_wall_ns" "$cpu" | tee -a "$raw"
    done
  done
  printf 'PAIR_END pair=%d utc=%s\n' "$pair" "$(date -u +%FT%TZ)" | tee -a "$raw"
done

printf 'SESSION_END utc=%s\n' "$(date -u +%FT%TZ)" | tee -a "$raw"
"$(dirname "${BASH_SOURCE[0]}")/summarize.py" "$raw" > "$output_dir/summary.txt"
