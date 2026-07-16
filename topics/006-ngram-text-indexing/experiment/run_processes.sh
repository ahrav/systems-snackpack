#!/usr/bin/env bash
set -euo pipefail

root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)
output_dir=${1:-/tmp/systems-snackpack-topic-006}
cpu=${CPU:-0}
processes=${PROCESSES:-12}

if (( processes < 4 || processes % 4 != 0 )); then
  echo "PROCESSES must be a positive multiple of four" >&2
  exit 2
fi

mkdir -p "$output_dir"
cd "$root"

export RUSTFLAGS="-C target-cpu=native -C debuginfo=1"
raw="$output_dir/processes.txt"
env_record="$output_dir/host-env.txt"

{
  printf 'captured_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'host=%s\n' "$(hostname -f 2>/dev/null || hostname)"
  printf 'cpu=%s\n' "$cpu"
  printf 'processes=%s\n' "$processes"
  printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
  uname -a
  lscpu
  printf 'nproc=' && nproc
  printf 'cpuset=' && taskset -pc $$
  rustc -Vv
  cargo -V
  gcc --version | head -n 1
  rustc -C target-cpu=native --print cfg
} > "$env_record"

cargo bench --quiet -p systems-snackpack-topic-006 --bench selectivity --no-run
# Pick the most recently built bench binary by mtime; a lexicographic sort on
# the hash suffix could silently select a stale artifact after partial cleans.
bench_binary=$(rg --files target/release/deps | rg '/selectivity-[0-9a-f]+$' | xargs -r ls -t | head -n 1)

: > "$raw"
{
  printf 'SESSION_START utc=%s host=%s cpu=%s processes=%s\n' \
    "$(date -u +%FT%TZ)" "$(hostname -f 2>/dev/null || hostname)" "$cpu" "$processes"
  sha256sum \
    topics/006-ngram-text-indexing/src/lib.rs \
    topics/006-ngram-text-indexing/benches/selectivity.rs \
    "$bench_binary"
  taskset -c "$cpu" "$bench_binary" --verify
} | tee -a "$raw"

for pair in $(seq 1 "$processes"); do
  case $(( (pair - 1) % 4 )) in
    0) first=scan; second=index; workload_order=selective-first ;;
    1) first=index; second=scan; workload_order=selective-first ;;
    2) first=scan; second=index; workload_order=common-first ;;
    3) first=index; second=scan; workload_order=common-first ;;
  esac

  printf 'PAIR_START pair=%d method_order=%s-%s workload_order=%s utc=%s\n' \
    "$pair" "$first" "$second" "$workload_order" "$(date -u +%FT%TZ)" | tee -a "$raw"
  taskset -c "$cpu" "$bench_binary" --method "$first" --workload-order "$workload_order" | tee -a "$raw"
  taskset -c "$cpu" "$bench_binary" --method "$second" --workload-order "$workload_order" | tee -a "$raw"
  printf 'PAIR_END pair=%d utc=%s\n' "$pair" "$(date -u +%FT%TZ)" | tee -a "$raw"
done

printf 'SESSION_END utc=%s\n' "$(date -u +%FT%TZ)" | tee -a "$raw"
