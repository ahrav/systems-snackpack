#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
root=$(cd "$script_dir/../../.." && pwd)
output_dir=${1:-/tmp/systems-snackpack-topic-008}
pairs=${PAIRS:-12}
mib=${MIB:-256}
passes=${PASSES:-64}
mprotect_pairs=${MPROTECT_PAIRS:-20000}
host_alias=${HOST_ALIAS:-unrecorded}
source_commit=${SOURCE_COMMIT:-}
source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unrecorded}

for value_name in pairs mib passes mprotect_pairs; do
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
if (( mib == 0 || passes == 0 || mprotect_pairs == 0 )); then
  echo "MIB, PASSES, and MPROTECT_PAIRS must be nonzero" >&2
  exit 2
fi
if (( mib % 2 != 0 )); then
  echo "MIB must be a multiple of the 2 MiB PMD size" >&2
  exit 2
fi

for command_name in cargo date dirname getconf git gzip hostname jq lscpu mkdir nm nproc \
  objdump perf python3 readelf rg rustc sed seq sha256sum tail taskset tee tr uname; do
  if ! command -v "$command_name" >/dev/null; then
    echo "required command not found: $command_name" >&2
    exit 2
  fi
done

base_page_bytes=$(getconf PAGESIZE)
if [[ ! -r /sys/kernel/mm/transparent_hugepage/hpage_pmd_size ]]; then
  echo "required PMD THP geometry file is unavailable" >&2
  exit 2
fi
pmd_page_bytes=$(tr -d '[:space:]' < /sys/kernel/mm/transparent_hugepage/hpage_pmd_size)
if [[ $base_page_bytes != 4096 || $pmd_page_bytes != 2097152 ]]; then
  echo "experiment requires 4096-byte base pages and 2097152-byte PMD THPs; host reports $base_page_bytes and $pmd_page_bytes bytes" >&2
  exit 2
fi

if [[ -z $source_commit ]] && git -C "$root" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  source_commit=$(git -C "$root" rev-parse HEAD)
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT must be the 40-digit source-candidate commit" >&2
  exit 2
fi

mkdir -p "$output_dir" "$output_dir/gates"
output_dir=$(cd "$output_dir" && pwd)
rm -f \
  "$output_dir/processes.txt" \
  "$output_dir/summary.txt" \
  "$output_dir/host-env.txt" \
  "$output_dir/correctness-example.log" \
  "$output_dir/benchmark-verify.log" \
  "$output_dir/pmu-events.txt" \
  "$output_dir/pmu-reach-base.log" \
  "$output_dir/pmu-reach-thp.log" \
  "$output_dir/codegen-focus.txt" \
  "$output_dir/codegen-full.txt.gz" \
  "$output_dir/benchmark-binary-symbols.txt" \
  "$output_dir/benchmark-binary-readelf.txt" \
  "$output_dir/benchmark-binary.sha256" \
  "$output_dir/source-files.sha256" \
  "$output_dir/run-manifest.txt"
rm -f "$output_dir/gates/"*.log
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
for ((required_cpu = cpu; required_cpu <= cpu + 16; required_cpu++)); do
  if ! taskset -c "$required_cpu" true >/dev/null 2>&1; then
    echo "shootdown workload requires CPUs $cpu through $((cpu + 16)) to be allowed; CPU $required_cpu is unavailable" >&2
    exit 2
  fi
done

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
  printf 'reader_cpu_range=%s-%s\n' "$((cpu + 1))" "$((cpu + 16))"
  printf 'pairs=%s\n' "$pairs"
  printf 'mib=%s\n' "$mib"
  printf 'passes=%s\n' "$passes"
  printf 'mprotect_pairs=%s\n' "$mprotect_pairs"
  printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
  printf 'base_page_bytes=%s\n' "$base_page_bytes"
  printf 'thp_enabled=' && tr '\n' ' ' < /sys/kernel/mm/transparent_hugepage/enabled && printf '\n'
  printf 'thp_defrag=' && tr '\n' ' ' < /sys/kernel/mm/transparent_hugepage/defrag && printf '\n'
  printf 'thp_pmd_size=%s\n' "$pmd_page_bytes"
  printf 'cpus_allowed=' && taskset -pc $$
  uname -a
  lscpu
  printf 'online_cpus=' && nproc
  rustc -Vv
  cargo -V
  gcc --version 2>/dev/null || echo 'gcc=absent'
  perf --version
  objdump --version | sed -n '1p'
  rustc -C target-cpu=native --print cfg
} > "$output_dir/host-env.txt"

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

cargo run --quiet -p systems-snackpack-topic-008 --example check_translation \
  > "$output_dir/correctness-example.log" 2>&1

bench_binary=$(
  cargo bench --message-format=json --quiet -p systems-snackpack-topic-008 \
    --bench address_translation --no-run \
    | jq -r 'select(.reason == "compiler-artifact"
        and .target.name == "address_translation"
        and (.target.kind | index("bench")))
        | .executable // empty' \
    | tail -n 1
)
if [[ -z $bench_binary || ! -x $bench_binary ]]; then
  echo "failed to locate the address_translation bench binary from Cargo JSON" >&2
  exit 1
fi

taskset -c "$cpu" "$bench_binary" --verify > "$output_dir/benchmark-verify.log" 2>&1
sha256sum "$bench_binary" > "$output_dir/benchmark-binary.sha256"
sha256sum \
  topics/008-tlbs-address-translation/src/lib.rs \
  topics/008-tlbs-address-translation/benches/address_translation.rs \
  topics/008-tlbs-address-translation/examples/check_translation.rs \
  topics/008-tlbs-address-translation/experiment/run_processes.sh \
  topics/008-tlbs-address-translation/experiment/summarize.py \
  > "$output_dir/source-files.sha256"
nm -anC "$bench_binary" > "$output_dir/benchmark-binary-symbols.txt"
readelf -n "$bench_binary" > "$output_dir/benchmark-binary-readelf.txt"
objdump -Cd --no-show-raw-insn "$bench_binary" | gzip -9 > "$output_dir/codegen-full.txt.gz"
gzip -dc "$output_dir/codegen-full.txt.gz" \
  | rg -A 48 -B 4 '<topic008_chase_pages>' \
  > "$output_dir/codegen-focus.txt"
if [[ ! -s $output_dir/codegen-focus.txt ]]; then
  echo "linked binary did not contain topic008_chase_pages" >&2
  exit 1
fi

perf list | rg -i -A 2 -B 1 'dtlb|itlb|tlb.*walk|translation' \
  > "$output_dir/pmu-events.txt" || true
arch=$(uname -m)
case $arch in
  aarch64)
    translation_events='armv8_pmuv3_0/l1d_tlb_refill/,armv8_pmuv3_0/l2d_tlb_refill/,armv8_pmuv3_0/dtlb_walk/'
    ;;
  x86_64)
    translation_events='l1_dtlb_misses,l2_dtlb_misses'
    ;;
  *)
    translation_events='dTLB-load-misses'
    ;;
esac
for variant in base thp; do
  if perf stat -x, -e "cycles,instructions,page-faults,task-clock,$translation_events" \
    -- taskset -c "$cpu" "$bench_binary" \
      --workload reach --variant "$variant" --mib "$mib" --passes 16 \
      --pair 0 --order 0 \
      > "$output_dir/pmu-reach-$variant.log" 2>&1; then
    printf 'pmu_%s_status=ok\n' "$variant" >> "$output_dir/run-manifest.txt"
  else
    printf 'pmu_%s_status=failed\n' "$variant" >> "$output_dir/run-manifest.txt"
  fi
done

raw="$output_dir/processes.txt"
: > "$raw"
{
  printf 'SESSION_START utc=%s host_alias=%s host=%s cpu=%s pairs=%s mib=%s passes=%s mprotect_pairs=%s source_commit=%s\n' \
    "$(date -u +%FT%TZ)" "$host_alias" "$(hostname -f 2>/dev/null || hostname)" \
    "$cpu" "$pairs" "$mib" "$passes" "$mprotect_pairs" "$source_commit"
  cat "$output_dir/benchmark-binary.sha256"
  cat "$output_dir/source-files.sha256"
  cat "$output_dir/benchmark-verify.log"
} | tee -a "$raw"

for pair in $(seq 1 "$pairs"); do
  if (( pair % 2 == 1 )); then
    reach_variants=(base thp)
    reader_counts=(1 16)
  else
    reach_variants=(thp base)
    reader_counts=(16 1)
  fi
  printf 'PAIR_START pair=%d reach_order=%s,%s shootdown_order=%s,%s utc=%s\n' \
    "$pair" "${reach_variants[0]}" "${reach_variants[1]}" \
    "${reader_counts[0]}" "${reader_counts[1]}" "$(date -u +%FT%TZ)" \
    | tee -a "$raw"

  for order in 0 1; do
    variant=${reach_variants[$order]}
    external_start=$(date +%s%N)
    result=$(taskset -c "$cpu" "$bench_binary" \
      --workload reach --variant "$variant" --mib "$mib" --passes "$passes" \
      --pair "$pair" --order "$((order + 1))")
    external_wall_ns=$(( $(date +%s%N) - external_start ))
    printf '%s external_wall_ns=%d cpu=%d\n' "$result" "$external_wall_ns" "$cpu" \
      | tee -a "$raw"
  done

  for order in 0 1; do
    readers=${reader_counts[$order]}
    external_start=$(date +%s%N)
    result=$(taskset -c "$cpu" "$bench_binary" \
      --workload shootdown --readers "$readers" \
      --mprotect-pairs "$mprotect_pairs" --first-cpu "$cpu" \
      --pair "$pair" --order "$((order + 1))")
    external_wall_ns=$(( $(date +%s%N) - external_start ))
    printf '%s external_wall_ns=%d cpu=%d\n' "$result" "$external_wall_ns" "$cpu" \
      | tee -a "$raw"
  done
  printf 'PAIR_END pair=%d utc=%s\n' "$pair" "$(date -u +%FT%TZ)" | tee -a "$raw"
done

printf 'SESSION_END utc=%s\n' "$(date -u +%FT%TZ)" | tee -a "$raw"
"$script_dir/summarize.py" "$raw" > "$output_dir/summary.txt"

{
  printf 'completed_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'benchmark_binary=%s\n' "$bench_binary"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'process_replication=12 paired order-balanced fresh processes per comparison\n'
  printf 'timing_boundary=setup warmup timed run-to-pre-emit external-launch-to-exit recorded separately\n'
} >> "$output_dir/run-manifest.txt"
