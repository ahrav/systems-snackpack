#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 4 ]]; then
  printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY HOST_LABEL SOURCE_COMMIT\n' "$0" >&2
  exit 2
fi

repository_root=$(cd "$1" && pwd -P)
output_directory=$2
host_label=$3
source_commit=$4
topic=topics/023-lock-free-reclamation-aba

: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the transferred Git archive}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the sender's archive digest}"
: "${SOURCE_TREE_MANIFEST_SHA256:?set SOURCE_TREE_MANIFEST_SHA256 to the sender's manifest digest}"

if [[ -e $output_directory ]]; then
  printf 'output directory already exists: %s\n' "$output_directory" >&2
  exit 2
fi
mkdir -p "$output_directory"/{codegen,correctness,gates,processes}

allowed_list=$(awk '/Cpus_allowed_list/ {print $2}' /proc/self/status)
cpu=${allowed_list%%,*}
cpu=${cpu%%-*}
started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)

cd "$repository_root"

actual_archive_sha256=$(sha256sum "$SOURCE_ARCHIVE_PATH" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$SOURCE_ARCHIVE_SHA256" ]]; then
  printf 'archive digest mismatch: expected %s, observed %s\n' \
    "$SOURCE_ARCHIVE_SHA256" "$actual_archive_sha256" >&2
  exit 2
fi
rg --files -g '!target/**' | LC_ALL=C sort | xargs sha256sum \
  >"$output_directory/source-tree.before.sha256"
actual_manifest_sha256=$(sha256sum "$output_directory/source-tree.before.sha256" | awk '{print $1}')
if [[ $actual_manifest_sha256 != "$SOURCE_TREE_MANIFEST_SHA256" ]]; then
  printf 'source manifest mismatch: expected %s, observed %s\n' \
    "$SOURCE_TREE_MANIFEST_SHA256" "$actual_manifest_sha256" >&2
  exit 2
fi

{
  printf 'run_started_utc=%s\n' "$started_utc"
  printf 'host_label=%s\n' "$host_label"
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_path=%s\n' "$SOURCE_ARCHIVE_PATH"
  printf 'source_archive_sha256=%s\n' "$actual_archive_sha256"
  printf 'source_tree_manifest_sha256=%s\n' "$actual_manifest_sha256"
  printf 'hostname_fqdn=%s\n' "$(hostname -f)"
  printf 'uname=%s\n' "$(uname -a)"
  printf 'architecture=%s\n' "$(uname -m)"
  printf 'kernel=%s\n' "$(uname -r)"
  printf 'configured_cpus=%s\n' "$(nproc --all)"
  printf 'available_cpus=%s\n' "$(nproc)"
  printf 'allowed_cpu_list=%s\n' "$allowed_list"
  printf 'selected_cpu=%s\n' "$cpu"
  lscpu
  awk -F: '/^(CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision)/ { if (!seen[$1]++) print }' /proc/cpuinfo
  if [[ -r /sys/devices/system/cpu/cpu0/regs/identification/midr_el1 ]]; then
    printf 'MIDR_EL1=%s\n' "$(</sys/devices/system/cpu/cpu0/regs/identification/midr_el1)"
  fi
  rustc -vV
  cargo -V
  printf 'gcc=%s\n' "$(gcc -dumpfullversion -dumpversion)"
  rustc -C target-cpu=native --print cfg | rg '^(target_arch|target_feature|target_has_atomic|target_pointer_width)'
  printf 'RUSTFLAGS=%s\n' "${RUSTFLAGS-<unset>}"
} >"$output_directory/host.txt"

rg --files "$topic" | LC_ALL=C sort | xargs sha256sum >"$output_directory/source-files.sha256"

if git rev-parse --git-dir >/dev/null 2>&1; then
  git diff --check >"$output_directory/gates/git-diff-check.log" 2>&1
else
  printf 'not applicable: extracted Git archive has no index\n' \
    >"$output_directory/gates/git-diff-check.log"
fi
cargo fmt --all -- --check >"$output_directory/gates/cargo-fmt.log" 2>&1
cargo test --workspace --lib --examples >"$output_directory/gates/cargo-test-lib-examples.log" 2>&1
cargo test --workspace --doc >"$output_directory/gates/cargo-test-doc.log" 2>&1
cargo clippy --workspace --all-targets -- -D warnings >"$output_directory/gates/cargo-clippy.log" 2>&1
cargo bench --workspace --no-run >"$output_directory/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps >"$output_directory/gates/cargo-doc.log" 2>&1
PYTHONPYCACHEPREFIX="$output_directory/pycache" \
  python3 -m py_compile "$topic/experiment/run_processes.py" "$topic/experiment/validate_receipts.py"
bash -n "$topic/experiment/run_host.sh"

native_target="$repository_root/../native-target"
RUSTFLAGS='-C target-cpu=native -C codegen-units=1' \
  cargo build --release -p lock-free-reclamation-aba --bin aba_lab \
  --target-dir "$native_target" >"$output_directory/build.log" 2>&1
binary="$native_target/release/aba_lab"
sha256sum "$binary" >"$output_directory/binary.sha256"

for replicate in {1..32}; do
  taskset --cpu-list "$cpu" "$binary" check
done >"$output_directory/correctness/replicates.txt"

objdump -d -C "$binary" >"$output_directory/codegen/final-binary.txt"
rg -n -A 80 '<bench_(raw|tagged)_kernel>' "$output_directory/codegen/final-binary.txt" \
  >"$output_directory/codegen/kernels.txt"

python3 "$topic/experiment/run_processes.py" \
  "$binary" "$output_directory/processes" "$cpu" --iterations 5000000 \
  >"$output_directory/process-driver.log"
python3 "$topic/experiment/validate_receipts.py" "$output_directory" \
  >"$output_directory/receipt-validation.txt"

rg --files -g '!target/**' | LC_ALL=C sort | xargs sha256sum \
  >"$output_directory/source-tree.after.sha256"
cmp "$output_directory/source-tree.before.sha256" "$output_directory/source-tree.after.sha256"

{
  printf 'Fresh process per treatment application.\n'
  printf 'Startup and warmup are outside the timed region.\n'
  printf 'Each timed process runs 5,000,000 iterations with two successful 64-bit CAS operations per iteration.\n'
  printf 'The atomic is private, hot, uncontended, and pinned to CPU %s.\n' "$cpu"
  printf 'The run does not measure reclamation, allocation, destruction, stalls, or contention.\n'
} >"$output_directory/measurement-boundary.txt"

run_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
printf 'run_finished_utc=%s\n' "$run_finished_utc" >>"$output_directory/host.txt"
(
  cd "$output_directory"
  rg --files -g '!evidence.sha256' | LC_ALL=C sort | xargs sha256sum >evidence.sha256
)
