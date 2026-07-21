#!/usr/bin/env bash
set -euo pipefail

if (( $# < 4 || $# > 7 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [CPU] [PROCESSES] [SAMPLES]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
cpu=${5:-0}
processes=${6:-12}
samples=${7:-500}

if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT must be a 40-character lowercase SHA-1" >&2
  exit 2
fi
if [[ ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
  echo "SOURCE_ARCHIVE_SHA256 must be a 64-character lowercase SHA-256" >&2
  exit 2
fi
if [[ $output_dir != /* ]]; then
  echo "OUTPUT_DIR must be an absolute path" >&2
  exit 2
fi
if (( cpu != 0 || processes != 12 || samples != 500 )); then
  echo "recorded runs require CPU 0, 12 processes, and 500 samples" >&2
  exit 2
fi
if [[ -z ${SOURCE_ARCHIVE:-} || $SOURCE_ARCHIVE != /* || ! -f $SOURCE_ARCHIVE ]]; then
  echo "SOURCE_ARCHIVE must name an absolute, readable Git archive" >&2
  exit 2
fi

observed_archive_sha=$(sha256sum "$SOURCE_ARCHIVE" | awk '{print $1}')
if [[ $observed_archive_sha != "$source_archive_sha256" ]]; then
  echo "source archive SHA-256 mismatch" >&2
  exit 2
fi
archive_tar=$(mktemp)
trap 'rm -f -- "$archive_tar"' EXIT
gzip -dc "$SOURCE_ARCHIVE" >"$archive_tar"
archive_commit=$(git get-tar-commit-id <"$archive_tar")
rm -f -- "$archive_tar"
trap - EXIT
if [[ $archive_commit != "$source_commit" ]]; then
  echo "source archive commit differs from SOURCE_COMMIT" >&2
  exit 2
fi

mkdir -p -- "$output_dir"
output_dir=$(cd -- "$output_dir" && pwd)

if [[ -z ${TOPIC11_INTERNAL_MARKER:-} ]]; then
  # Re-enter from a verified extraction so the checkout cannot affect the build.
  extracted_root=$(mktemp -d)
  internal_marker=$(mktemp)
  printf '%s\t%s\t%s\n' "$extracted_root" "$source_commit" "$source_archive_sha256" \
    >"$internal_marker"
  trap 'rm -rf -- "$extracted_root"; rm -f -- "$internal_marker"' EXIT
  tar -xzf "$SOURCE_ARCHIVE" -C "$extracted_root"
  child_status=0
  env TOPIC11_INTERNAL_MARKER="$internal_marker" SOURCE_ARCHIVE="$SOURCE_ARCHIVE" \
    "$extracted_root/topics/011-cycle-accurate-measurement/experiment/run_processes.sh" "$@" \
    || child_status=$?
  rm -rf -- "$extracted_root"
  rm -f -- "$internal_marker"
  trap - EXIT
  exit "$child_status"
fi

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_root=$(cd -- "$script_dir/../../.." && pwd)
if [[ ! -r $TOPIC11_INTERNAL_MARKER ]]; then
  echo "internal archive marker is missing" >&2
  exit 2
fi
IFS=$'\t' read -r marker_root marker_commit marker_sha <"$TOPIC11_INTERNAL_MARKER"
if [[ $repo_root != "$marker_root" || $source_commit != "$marker_commit" \
  || $source_archive_sha256 != "$marker_sha" ]]; then
  echo "measurement tree is not bound to the verified source archive" >&2
  exit 2
fi
cd -- "$repo_root"

mkdir -p -- "$output_dir/gates"

# Prevent inherited encoded flags and compiler wrappers from changing the build.
unset CARGO_ENCODED_RUSTFLAGS RUSTC_WORKSPACE_WRAPPER RUSTC_WRAPPER
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C codegen-units=1"

cargo fmt --all -- --check >"$output_dir/gates/cargo-fmt.log" 2>&1
cargo test --workspace --lib --examples >"$output_dir/gates/cargo-test-lib-examples.log" 2>&1
cargo test --workspace --doc >"$output_dir/gates/cargo-test-doc.log" 2>&1
cargo clippy --workspace --all-targets -- -D warnings >"$output_dir/gates/cargo-clippy.log" 2>&1
cargo bench --workspace --no-run >"$output_dir/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps >"$output_dir/gates/cargo-doc.log" 2>&1

cargo build --release -p systems-snackpack-topic-011 --bench cycle_probe \
  --message-format=json-render-diagnostics >"$output_dir/cargo-build.jsonl" 2>"$output_dir/cargo-build.stderr"
benchmark=$(python3 "$script_dir/summarize.py" --locate-bench cycle_probe systems-snackpack-topic-011 \
  <"$output_dir/cargo-build.jsonl")

taskset -c "$cpu" "$benchmark" --verify >"$output_dir/benchmark-verify.log" 2>&1
taskset -c "$cpu" "$benchmark" --probe >"$output_dir/counter-probe.log" 2>&1

sha256sum "$benchmark" >"$output_dir/benchmark-binary.sha256"
readelf -h "$benchmark" >"$output_dir/benchmark-binary-readelf.txt"
nm -an "$benchmark" >"$output_dir/benchmark-binary-symbols.txt"
objdump -d -C --no-show-raw-insn "$benchmark" >"$output_dir/codegen-full.txt"
# Gate the counter bracket and recurrence body independently.
awk '/<cycle_probe::linux::read_counter>:/ { capture = 1 } capture { print } capture && /^$/ { exit }' \
  "$output_dir/codegen-full.txt" >"$output_dir/codegen-counter-function.txt"
rg -q '<cycle_probe::linux::read_counter>:' "$output_dir/codegen-counter-function.txt"
if rg -q 'bracket=mfence-rdtsc-mfence' "$output_dir/counter-probe.log"; then
  rg -n -U 'mfence\n[^\n]*rdtsc\n[^\n]*mfence' \
    "$output_dir/codegen-counter-function.txt" >"$output_dir/codegen-counter.txt"
elif rg -q 'bracket=lfence-rdtsc-lfence' "$output_dir/counter-probe.log"; then
  rg -n -U 'lfence\n[^\n]*rdtsc\n[^\n]*lfence' \
    "$output_dir/codegen-counter-function.txt" >"$output_dir/codegen-counter.txt"
elif rg -q 'bracket=isb-mrs-cntvct-isb' "$output_dir/counter-probe.log"; then
  rg -n -U 'isb\n[^\n]*mrs[^\n]*cntvct_el0\n[^\n]*isb' \
    "$output_dir/codegen-counter-function.txt" >"$output_dir/codegen-counter.txt"
else
  echo "counter probe reported an unknown bracket" >&2
  exit 2
fi
awk '/<systems_snackpack_topic_011::dependent_chain>:/ { capture = 1 } capture { print } capture && /^$/ { exit }' \
  "$output_dir/codegen-full.txt" >"$output_dir/codegen-workload.txt"
rg -q '<systems_snackpack_topic_011::dependent_chain>:' "$output_dir/codegen-workload.txt"
rg -q 'imul|\bmul\b' "$output_dir/codegen-workload.txt"
{
  awk '1' "$output_dir/codegen-counter.txt"
  awk '1' "$output_dir/codegen-workload.txt"
} >"$output_dir/codegen-focus.txt"
gzip -9 "$output_dir/codegen-full.txt"

{
  printf 'host_alias=%s\n' "$host_alias"
  printf 'resolved_hostname=%s\n' "$(hostname -f)"
  printf 'utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  printf 'uname='; uname -a
  printf 'online_cpus='; getconf _NPROCESSORS_ONLN
  lscpu
  printf '\nrustc\n'; rustc -Vv
  printf '\ncargo\n'; cargo -V
  printf '\ncc\n'; cc --version
  printf '\nlinker\n'; ld --version
  printf '\nobjdump\n'; objdump --version
  printf '\nnative_target_cfg\n'; rustc -C target-cpu=native --print cfg
  printf '\nclocksource\n'; awk '1' /sys/devices/system/clocksource/clocksource0/current_clocksource
  printf '\navailable_clocksources\n'; awk '1' /sys/devices/system/clocksource/clocksource0/available_clocksource
  printf '\nperf_event_paranoid\n'; awk '1' /proc/sys/kernel/perf_event_paranoid
  printf '\nperf_user_access\n'; awk '1' /proc/sys/kernel/perf_user_access 2>/dev/null || true
  printf '\nrdpmc\n'; awk '1' /sys/bus/event_source/devices/cpu/rdpmc 2>/dev/null || true
  printf '\nenvironment_flags\n'
  env | rg '^(CARGO_BUILD_TARGET|CARGO_ENCODED_RUSTFLAGS|CFLAGS|CPPFLAGS|CXXFLAGS|RUSTC_WORKSPACE_WRAPPER|RUSTC_WRAPPER|RUSTDOCFLAGS|RUSTFLAGS)=' | sort || true
  printf 'cargo_encoded_rustflags=unset\n'
  printf 'rustc_wrapper=unset\n'
  printf 'rustc_workspace_wrapper=unset\n'
} >"$output_dir/host-env.txt"

{
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_commit=%s\n' "$archive_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'host_alias=%s\n' "$host_alias"
  printf 'cpu=%s\n' "$cpu"
  printf 'processes=%s\n' "$processes"
  printf 'samples=%s\n' "$samples"
  printf 'rustflags=%s\n' "$RUSTFLAGS"
} >"$output_dir/run-manifest.txt"

{
  printf 'SESSION_START host_alias=%s source_commit=%s source_archive_sha256=%s cpu=%s processes=%s samples=%s\n' \
    "$host_alias" "$source_commit" "$source_archive_sha256" "$cpu" "$processes" "$samples"
  printf 'ARTIFACT benchmark_binary_sha256=%s\n' "$(awk '{print $1}' "$output_dir/benchmark-binary.sha256")"
  awk '1' "$output_dir/counter-probe.log"
} >"$output_dir/processes.txt"

orders=(
  raw-first clock-first clock-first raw-first
  raw-first clock-first clock-first raw-first
  raw-first clock-first clock-first raw-first
)

for (( index = 0; index < processes; index++ )); do
  order=${orders[$index]}
  process_number=$((index + 1))
  printf 'PROCESS_START index=%s order=%s\n' "$process_number" "$order" >>"$output_dir/processes.txt"
  launched=$(date +%s%N)
  taskset -c "$cpu" "$benchmark" "$order" "$samples" >>"$output_dir/processes.txt" 2>&1
  exited=$(date +%s%N)
  printf 'PROCESS_END index=%s order=%s external_wall_ns=%s\n' \
    "$process_number" "$order" "$((exited - launched))" >>"$output_dir/processes.txt"
done
printf 'SESSION_END processes=%s\n' "$processes" >>"$output_dir/processes.txt"

python3 "$script_dir/summarize.py" "$output_dir/processes.txt" >"$output_dir/summary.txt"

{
  rg --files Cargo.toml Cargo.lock rust-toolchain.toml topics/011-cycle-accurate-measurement
} | sort | xargs sha256sum >"$output_dir/source-files.sha256"

printf 'evidence_dir=%s\n' "$output_dir"
awk '1' "$output_dir/summary.txt"
