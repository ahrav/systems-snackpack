#!/usr/bin/env bash
set -euo pipefail

if (( $# < 4 || $# > 8 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [CPU] [PAIRS] [BIT_POWER] [QUERIES]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
cpu=${5:-0}
pairs=${6:-12}
bit_power=${7:-26}
queries=${8:-4000000}

if [[ $(uname -s) != Linux ]]; then
  echo "the process runner requires Linux" >&2
  exit 2
fi
if (( pairs != 12 )); then
  echo "the recorded interval requires exactly 12 pairs" >&2
  exit 2
fi
for command in cargo rustc taskset rg jq nm readelf objdump gzip sha256sum python3; do
  if ! command -v "$command" >/dev/null 2>&1; then
    echo "required command is unavailable: $command" >&2
    exit 2
  fi
done
if ! taskset -c "$cpu" true >/dev/null 2>&1; then
  echo "CPU $cpu is outside this process's allowed affinity mask" >&2
  exit 2
fi

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd "$script_dir/../../.." && pwd)
cd "$repo_root"
mkdir -p "$output_dir/gates"

export CARGO_TARGET_DIR="$output_dir/target"
unset CARGO_ENCODED_RUSTFLAGS
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C codegen-units=1"

{
  printf 'captured_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'host_alias=%s\n' "$host_alias"
  printf 'resolved_host=%s\n' "$(hostname -f 2>/dev/null || hostname)"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'cpu=%s\n' "$cpu"
  printf 'pairs=%s\n' "$pairs"
  printf 'bit_power=%s\n' "$bit_power"
  printf 'queries=%s\n' "$queries"
  printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
  printf 'cpus_allowed=' && taskset -pc $$
  uname -a
  printf 'uname_machine=' && uname -m
  printf 'kernel_release=' && uname -r
  lscpu
  printf 'available_cpus=' && nproc --all
  rustc -Vv
  cargo -V
  gcc --version 2>/dev/null || echo 'gcc=absent'
  if command -v clang >/dev/null 2>&1; then clang --version; else echo 'clang=absent'; fi
  if command -v rustup >/dev/null 2>&1; then rustup show active-toolchain; else echo 'rustup=absent'; fi
  objdump --version | sed -n '1p'
  rustc -C target-cpu=native --print cfg | rg '^target_(arch|endian|feature|pointer_width|vendor)'
} > "$output_dir/host-env.txt" 2>&1

run_gate() {
  local name=$1
  shift
  "$@" > "$output_dir/gates/$name.log" 2>&1
}

run_gate cargo-fmt cargo fmt --all -- --check
run_gate cargo-test-lib-examples cargo test --workspace --lib --examples
run_gate cargo-test-doc cargo test --workspace --doc
run_gate cargo-clippy cargo clippy --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --workspace --no-run
run_gate cargo-doc env RUSTDOCFLAGS=-D\ warnings cargo doc --workspace --no-deps

cargo run --quiet -p systems-snackpack-topic-009 --example check_equivalence -- "$bit_power" \
  > "$output_dir/correctness-example.log" 2>&1

bench_binary=$(
  cargo bench --message-format=json --quiet -p systems-snackpack-topic-009 \
    --bench succinct_rank --no-run \
    | jq -r 'select(.reason == "compiler-artifact"
        and .target.name == "succinct_rank"
        and (.target.kind | index("bench")))
        | .executable // empty' \
    | tail -n 1
)
if [[ -z $bench_binary || ! -x $bench_binary ]]; then
  echo "failed to locate the succinct_rank bench binary from Cargo JSON" >&2
  exit 1
fi

taskset -c "$cpu" "$bench_binary" --verify 20 > "$output_dir/benchmark-verify.log" 2>&1
sha256sum "$bench_binary" > "$output_dir/benchmark-binary.sha256"
sha256sum \
  topics/009-succinct-static-index-structures/src/lib.rs \
  topics/009-succinct-static-index-structures/benches/succinct_rank.rs \
  topics/009-succinct-static-index-structures/examples/check_equivalence.rs \
  topics/009-succinct-static-index-structures/experiment/run_processes.sh \
  topics/009-succinct-static-index-structures/experiment/summarize.py \
  > "$output_dir/source-files.sha256"
nm -anC "$bench_binary" > "$output_dir/benchmark-binary-symbols.txt"
readelf -n "$bench_binary" > "$output_dir/benchmark-binary-readelf.txt"
objdump -Cd --no-show-raw-insn "$bench_binary" | gzip -9 > "$output_dir/codegen-full.txt.gz"
gzip -dc "$output_dir/codegen-full.txt.gz" \
  | rg -A 48 -B 4 '<topic009_inspect_(compact|prefix)_rank>' \
  > "$output_dir/codegen-focus.txt"
for symbol in topic009_inspect_compact_rank topic009_inspect_prefix_rank; do
  if ! rg -q "<$symbol>" "$output_dir/codegen-focus.txt"; then
    echo "linked binary did not contain $symbol" >&2
    exit 1
  fi
done

raw="$output_dir/processes.txt"
: > "$raw"
{
  printf 'SESSION_START utc=%s host_alias=%s host=%s cpu=%s pairs=%s bit_power=%s queries=%s source_commit=%s\n' \
    "$(date -u +%FT%TZ)" "$host_alias" "$(hostname -f 2>/dev/null || hostname)" \
    "$cpu" "$pairs" "$bit_power" "$queries" "$source_commit"
  cat "$output_dir/benchmark-binary.sha256"
  cat "$output_dir/source-files.sha256"
  cat "$output_dir/benchmark-verify.log"
} | tee -a "$raw"

for pair in $(seq 1 "$pairs"); do
  if (( pair % 2 == 1 )); then
    order=compact-prefix
  else
    order=prefix-compact
  fi
  printf 'PAIR_START pair=%d order=%s utc=%s\n' \
    "$pair" "$order" "$(date -u +%FT%TZ)" | tee -a "$raw"
  external_start=$(date +%s%N)
  result=$(taskset -c "$cpu" "$bench_binary" --run "$order" "$queries" "$bit_power" "$pair")
  external_wall_ns=$(( $(date +%s%N) - external_start ))
  printf '%s external_wall_ns=%d cpu=%d\n' "$result" "$external_wall_ns" "$cpu" \
    | tee -a "$raw"
  printf 'PAIR_END pair=%d utc=%s\n' "$pair" "$(date -u +%FT%TZ)" | tee -a "$raw"
done

printf 'SESSION_END utc=%s\n' "$(date -u +%FT%TZ)" | tee -a "$raw"
"$script_dir/summarize.py" "$raw" > "$output_dir/summary.txt"

{
  printf 'completed_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'benchmark_binary=%s\n' "$bench_binary"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'process_replication=12 fresh paired order-balanced processes\n'
  printf 'timing_boundary=dataset clone index builds query build warmup timed queries and external launch-to-exit recorded separately\n'
} > "$output_dir/run-manifest.txt"
