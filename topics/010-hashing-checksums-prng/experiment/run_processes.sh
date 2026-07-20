#!/usr/bin/env bash
set -euo pipefail

if (( $# < 4 || $# > 9 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [CPU] [PAIRS] [LEN] [ALIGN] [ITERATIONS]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
cpu=${5:-0}
pairs=${6:-12}
length=${7:-4096}
alignment=${8:-3}
iterations=${9:-262144}

if [[ $(uname -s) != Linux ]]; then
  echo "the process runner requires Linux" >&2
  exit 2
fi
for value_name in cpu pairs length alignment iterations; do
  value=${!value_name}
  if [[ ! $value =~ ^(0|[1-9][0-9]*)$ ]]; then
    echo "$value_name must be an unsigned decimal integer, got: $value" >&2
    exit 2
  fi
done
if (( cpu != 0 )); then
  echo "the recorded experiment pins every process to CPU 0" >&2
  exit 2
fi
if (( pairs != 12 )); then
  echo "the balanced experiment requires exactly 12 pairs" >&2
  exit 2
fi
if (( length == 0 || iterations == 0 )); then
  echo "LEN and ITERATIONS must be nonzero" >&2
  exit 2
fi
if [[ ! $host_alias =~ ^[A-Za-z0-9._-]+$ ]]; then
  echo "HOST_ALIAS must contain only [A-Za-z0-9._-]" >&2
  exit 2
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT must be a 40-digit lowercase commit ID" >&2
  exit 2
fi
if [[ ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
  echo "SOURCE_ARCHIVE_SHA256 must be a 64-digit lowercase SHA-256" >&2
  exit 2
fi
for command_name in cargo date dirname env gcc git gzip hostname lscpu mkdir \
  nm nproc objdump python3 readelf rg rm rustc seq sha256sum taskset tee uname; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    echo "required command is unavailable: $command_name" >&2
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

# A Git checkout must be byte-for-byte at the declared candidate. A source
# archive has no .git directory, so its independently recorded archive digest
# is the provenance boundary for the remote run.
source_kind=archive
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  source_kind=git
  resolved_source_commit=$(git rev-parse --verify "$source_commit^{commit}" 2>/dev/null || true)
  if [[ $resolved_source_commit != "$source_commit" ]]; then
    echo "SOURCE_COMMIT does not resolve to the declared commit" >&2
    exit 2
  fi
  if ! git diff --quiet "$source_commit" -- \
    || [[ -n $(git ls-files --others --exclude-standard) ]]; then
    echo "working tree must exactly match SOURCE_COMMIT before measurement" >&2
    exit 2
  fi
fi

if [[ -L $output_dir ]]; then
  echo "output directory must not be a symbolic link: $output_dir" >&2
  exit 2
fi
mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
case "$output_dir" in
  "$repo_root"|"$repo_root"/*)
    echo "OUTPUT_DIR must be outside the source tree" >&2
    exit 2
    ;;
esac
if [[ -L $output_dir/gates ]]; then
  echo "output gates directory must not be a symbolic link" >&2
  exit 2
fi
mkdir -p "$output_dir/gates"

for artifact in processes.txt summary.txt host-env.txt correctness-example.log \
  benchmark-verify.log schema-smoke.txt codegen-focus.txt codegen-full.txt.gz \
  benchmark-binary-symbols.txt benchmark-binary-readelf.txt \
  benchmark-binary.sha256 source-files.sha256 run-manifest.txt; do
  rm -f "$output_dir/$artifact"
done
for gate in git-diff-check cargo-fmt cargo-test-lib-examples cargo-test-doc \
  cargo-clippy cargo-bench-no-run cargo-doc; do
  rm -f "$output_dir/gates/$gate.log"
done

export CARGO_TARGET_DIR="$output_dir/target"
export CARGO_INCREMENTAL=0
unset CARGO_ENCODED_RUSTFLAGS
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C codegen-units=1"

{
  printf 'captured_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'host_alias=%s\n' "$host_alias"
  printf 'host_fqdn=%s\n' "$(hostname -f 2>/dev/null || hostname)"
  printf 'source_kind=%s\n' "$source_kind"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'cpu=%s\n' "$cpu"
  printf 'pairs=%s\n' "$pairs"
  printf 'len=%s\n' "$length"
  printf 'align=%s\n' "$alignment"
  printf 'iterations=%s\n' "$iterations"
  printf 'RUSTFLAGS=%s\n' "$RUSTFLAGS"
  printf 'CARGO_INCREMENTAL=%s\n' "$CARGO_INCREMENTAL"
  printf 'uname_machine=' && uname -m
  printf 'kernel_release=' && uname -r
  uname -a
  lscpu
  printf 'available_cpus=' && nproc --all
  printf 'cpus_allowed=' && taskset -pc $$
  rustc -Vv
  cargo -V
  gcc --version 2>/dev/null || echo 'gcc=absent'
  if command -v clang >/dev/null 2>&1; then clang --version; else echo 'clang=absent'; fi
  if command -v rustup >/dev/null 2>&1; then rustup show active-toolchain; else echo 'rustup=absent'; fi
  objdump --version
  rustc -C target-cpu=native --print cfg | rg '^target_(arch|endian|feature|pointer_width|vendor)'
} > "$output_dir/host-env.txt" 2>&1

run_gate() {
  local name=$1
  shift
  "$@" > "$output_dir/gates/$name.log" 2>&1
}

if [[ $source_kind == git ]]; then
  run_gate git-diff-check git diff --check "$source_commit^" "$source_commit"
else
  printf 'not_applicable=source_archive_has_no_git_metadata\n' \
    > "$output_dir/gates/git-diff-check.log"
fi
run_gate cargo-fmt cargo fmt --all -- --check
run_gate cargo-test-lib-examples cargo test --workspace --lib --examples
run_gate cargo-test-doc cargo test --workspace --doc
run_gate cargo-clippy cargo clippy --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --workspace --no-run
run_gate cargo-doc env RUSTDOCFLAGS=-D\ warnings cargo doc --workspace --no-deps

cargo run --quiet -p systems-snackpack-topic-010 --example check_equivalence \
  > "$output_dir/correctness-example.log" 2>&1

bench_binary=$(
  cargo bench --message-format=json --quiet -p systems-snackpack-topic-010 \
    --bench crc32c --no-run \
    | python3 "$script_dir/summarize.py" --locate-bench crc32c
)
if [[ -z $bench_binary || ! -x $bench_binary ]]; then
  echo "failed to locate the executable crc32c bench binary" >&2
  exit 1
fi

taskset -c "$cpu" "$bench_binary" --verify \
  > "$output_dir/benchmark-verify.log" 2>&1
sha256sum "$bench_binary" > "$output_dir/benchmark-binary.sha256"
sha256sum \
  topics/010-hashing-checksums-prng/Cargo.toml \
  topics/010-hashing-checksums-prng/src/lib.rs \
  topics/010-hashing-checksums-prng/examples/check_equivalence.rs \
  topics/010-hashing-checksums-prng/benches/crc32c.rs \
  topics/010-hashing-checksums-prng/experiment/run_processes.sh \
  topics/010-hashing-checksums-prng/experiment/summarize.py \
  > "$output_dir/source-files.sha256"
nm -anC "$bench_binary" > "$output_dir/benchmark-binary-symbols.txt"
readelf -n "$bench_binary" > "$output_dir/benchmark-binary-readelf.txt"
objdump -Cd --no-show-raw-insn "$bench_binary" | gzip -9 \
  > "$output_dir/codegen-full.txt.gz"
gzip -dc "$output_dir/codegen-full.txt.gz" \
  | rg -A 64 -B 4 '<topic010_crc32c_(table|hardware)_update>' \
  > "$output_dir/codegen-focus.txt"
for symbol in topic010_crc32c_table_update topic010_crc32c_hardware_update; do
  if ! rg -q "<$symbol>" "$output_dir/codegen-focus.txt"; then
    echo "linked binary did not contain $symbol" >&2
    exit 1
  fi
done
if [[ $(uname -m) == x86_64 ]]; then
  if ! rg -q '\bcrc32[bwlq]?\b' "$output_dir/codegen-focus.txt"; then
    echo "x86-64 hardware boundary contains no CRC32 instruction" >&2
    exit 1
  fi
elif [[ $(uname -m) == aarch64 ]]; then
  if ! rg -q '\bcrc32c?[bwhx]\b' "$output_dir/codegen-focus.txt"; then
    echo "AArch64 hardware boundary contains no CRC32 instruction" >&2
    exit 1
  fi
else
  echo "unsupported architecture for required CRC codegen inspection: $(uname -m)" >&2
  exit 1
fi

run_one() {
  local mode=$1
  local pair=$2
  local order=$3
  local position=$4
  local measurement_iterations=${5:-$iterations}
  local started result external_wall_ns
  started=$(date +%s%N)
  result=$(taskset -c "$cpu" "$bench_binary" \
    --mode "$mode" --len "$length" --align "$alignment" \
    --iterations "$measurement_iterations")
  external_wall_ns=$(( $(date +%s%N) - started ))
  if [[ $result == *$'\n'* || ! $result =~ ^RESULT[[:space:]] ]]; then
    echo "bench process must emit exactly one RESULT line" >&2
    exit 1
  fi
  printf '%s pair=%d order=%s position=%d external_wall_ns=%d cpu=%d\n' \
    "$result" "$pair" "$order" "$position" "$external_wall_ns" "$cpu"
}

# Catch producer/parser schema drift before the measured 24-process session.
smoke="$output_dir/schema-smoke.txt"
{
  run_one table 1 table-hardware 1 1024
  run_one hardware 1 table-hardware 2 1024
} > "$smoke"
python3 "$script_dir/summarize.py" --schema-check "$smoke"

raw="$output_dir/processes.txt"
: > "$raw"
benchmark_binary_sha256=$(rg -o -m 1 '^[0-9a-f]{64}' "$output_dir/benchmark-binary.sha256")
{
  printf 'SESSION_START utc=%s host_alias=%s cpu=%s pairs=%s len=%s align=%s iterations=%s source_commit=%s source_archive_sha256=%s\n' \
    "$(date -u +%FT%TZ)" "$host_alias" "$cpu" "$pairs" "$length" \
    "$alignment" "$iterations" "$source_commit" "$source_archive_sha256"
  printf 'ARTIFACT benchmark_binary_sha256=%s\n' "$benchmark_binary_sha256"
} | tee -a "$raw"

for pair in $(seq 1 "$pairs"); do
  if (( pair % 2 == 1 )); then
    order=table-hardware
    modes=(table hardware)
  else
    order=hardware-table
    modes=(hardware table)
  fi
  printf 'PAIR_START pair=%d order=%s utc=%s\n' \
    "$pair" "$order" "$(date -u +%FT%TZ)" | tee -a "$raw"
  for position in 1 2; do
    run_one "${modes[$((position - 1))]}" "$pair" "$order" "$position" | tee -a "$raw"
  done
  printf 'PAIR_END pair=%d utc=%s\n' "$pair" "$(date -u +%FT%TZ)" | tee -a "$raw"
done

printf 'SESSION_END utc=%s\n' "$(date -u +%FT%TZ)" | tee -a "$raw"
python3 "$script_dir/summarize.py" "$raw" > "$output_dir/summary.txt"

{
  printf 'completed_utc=%s\n' "$(date -u +%FT%TZ)"
  printf 'benchmark_binary=%s\n' "$bench_binary"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'replication=12 order-balanced pairs; 24 fresh pinned processes\n'
  printf 'steady_state_boundary=each RESULT excludes data setup and the fixed warmup; it times len*iterations bytes\n'
  printf 'launch_to_exit_boundary=process startup + setup + warmup + timed loop + teardown; recorded separately and excluded from the throughput ratio\n'
} > "$output_dir/run-manifest.txt"
