#!/usr/bin/env bash
set -euo pipefail

if (( $# < 5 || $# > 8 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 FILE_DIR [CPU] [BLOCKS] [MIB]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
file_dir=$5
cpu=${6:-0}
blocks=${7:-8}
mib=${8:-32}

if [[ -z $host_alias || $host_alias =~ [[:cntrl:]] ]]; then
  echo "HOST_ALIAS must be nonempty and contain no control characters" >&2
  exit 2
fi

if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
  echo "SOURCE_COMMIT must be a 40-character lowercase SHA-1" >&2
  exit 2
fi
if [[ ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
  echo "SOURCE_ARCHIVE_SHA256 must be a 64-character lowercase SHA-256" >&2
  exit 2
fi
if [[ $output_dir != /* || $file_dir != /* ]]; then
  echo "OUTPUT_DIR and FILE_DIR must be absolute paths" >&2
  exit 2
fi
if [[ $cpu != 0 || $blocks != 8 || $mib != 32 ]]; then
  echo "recorded runs require CPU 0, eight blocks, and 32 MiB" >&2
  exit 2
fi
if [[ -z ${SOURCE_ARCHIVE:-} || $SOURCE_ARCHIVE != /* || ! -f $SOURCE_ARCHIVE ]]; then
  echo "SOURCE_ARCHIVE must name an absolute, readable source archive" >&2
  exit 2
fi
if [[ ! -d $file_dir || ! -w $file_dir ]]; then
  echo "FILE_DIR must be an existing writable directory" >&2
  exit 2
fi
for required_tool in awk cargo cc cp findmnt git gzip lscpu nm objdump python3 readelf rg rustc sha256sum sort tar taskset wc xargs; do
  if ! command -v "$required_tool" >/dev/null 2>&1; then
    echo "required tool is unavailable: $required_tool" >&2
    exit 2
  fi
done
for required_file in \
  /proc/cpuinfo \
  /proc/meminfo \
  /proc/sys/kernel/numa_balancing \
  /sys/kernel/mm/transparent_hugepage/enabled \
  /sys/kernel/mm/transparent_hugepage/defrag; do
  if [[ ! -r $required_file ]]; then
    echo "required host evidence is unreadable: $required_file" >&2
    exit 2
  fi
done

archive_gz=$(mktemp)
archive_tar=$(mktemp)
extracted_root=$(mktemp -d)
checksums_tmp=
cleanup() {
  rm -rf -- "$extracted_root"
  rm -f -- "$archive_gz" "$archive_tar"
  if [[ -n $checksums_tmp ]]; then
    rm -f -- "$checksums_tmp"
  fi
}
trap cleanup EXIT
cp -- "$SOURCE_ARCHIVE" "$archive_gz"
observed_archive_sha=$(sha256sum "$archive_gz" | awk '{print $1}')
if [[ $observed_archive_sha != "$source_archive_sha256" ]]; then
  echo "source archive SHA-256 mismatch" >&2
  exit 2
fi
gzip -dc "$archive_gz" >"$archive_tar"
archive_commit=$(git get-tar-commit-id <"$archive_tar")
if [[ $archive_commit != "$source_commit" ]]; then
  echo "source archive embedded commit differs from SOURCE_COMMIT" >&2
  exit 2
fi

tar -xf "$archive_tar" -C "$extracted_root"
mapfile -t workspace_manifests < <(rg -l '^\[workspace\]' "$extracted_root" -g Cargo.toml)
if (( ${#workspace_manifests[@]} != 1 )); then
  echo "archive must contain exactly one workspace Cargo.toml" >&2
  exit 2
fi
repo_root=$(dirname -- "${workspace_manifests[0]}")
script_dir="$repo_root/topics/012-mmap-page-faults/experiment"
archived_driver="$script_dir/run_processes.sh"
if [[ ! -r $archived_driver || ! -r $script_dir/vm_faults.c \
  || ! -r $script_dir/summarize.py || ! -r $script_dir/run_one.py ]]; then
  echo "verified archive does not contain the Topic 12 experiment" >&2
  exit 2
fi

case ${TOPIC12_ARCHIVED_STAGE:-} in
  '')
    child_status=0
    env TOPIC12_ARCHIVED_STAGE=1 SOURCE_ARCHIVE="$archive_gz" \
      "$archived_driver" "$@" || child_status=$?
    exit "$child_status"
    ;;
  1)
    running_driver_sha=$(sha256sum "${BASH_SOURCE[0]}" | awk '{print $1}')
    archived_driver_sha=$(sha256sum "$archived_driver" | awk '{print $1}')
    if [[ $running_driver_sha != "$archived_driver_sha" ]]; then
      echo "executing driver differs from the source archive" >&2
      exit 2
    fi
    ;;
  *)
    echo "invalid internal archive stage" >&2
    exit 2
    ;;
esac

file_fstype=$(findmnt -n -o FSTYPE -T "$file_dir")
case "$file_fstype" in
  tmpfs|ramfs)
    echo "FILE_DIR must not use $file_fstype" >&2
    exit 2
    ;;
esac

if [[ -d $output_dir ]] && (( $(rg --files -uu -0 "$output_dir" | wc -c) != 0 )); then
  echo "OUTPUT_DIR must be absent or empty" >&2
  exit 2
fi
mkdir -p -- "$output_dir/gates"
output_dir=$(cd -- "$output_dir" && pwd)
cd -- "$repo_root"

{
  rg --files -uu -0 Cargo.toml Cargo.lock rust-toolchain.toml topics/012-mmap-page-faults
} | sort -z | xargs -0 sha256sum >"$output_dir/source-files.sha256"

unset CARGO_ENCODED_RUSTFLAGS RUSTC_WORKSPACE_WRAPPER RUSTC_WRAPPER
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C codegen-units=1"

cargo fmt --all -- --check >"$output_dir/gates/cargo-fmt.log" 2>&1
cargo test --locked --workspace --lib --examples >"$output_dir/gates/cargo-test-lib-examples.log" 2>&1
cargo test --locked --workspace --doc >"$output_dir/gates/cargo-test-doc.log" 2>&1
cargo clippy --locked --workspace --all-targets -- -D warnings >"$output_dir/gates/cargo-clippy.log" 2>&1
cargo bench --locked --workspace --no-run >"$output_dir/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS="-D warnings" cargo doc --locked --workspace --no-deps >"$output_dir/gates/cargo-doc.log" 2>&1

cargo run --locked -p systems-snackpack-topic-012 --example check_contracts \
  >"$output_dir/example-check.log" 2>&1
cargo bench --locked -p systems-snackpack-topic-012 --bench fault_cost_model \
  >"$output_dir/rust-benchmark.log" 2>&1

c_flags=(-O3 -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer -march=native)
cc "${c_flags[@]}" "$script_dir/vm_faults.c" -o "$output_dir/vm_faults"
(cd -- "$output_dir" && sha256sum vm_faults >vm_faults.sha256)
readelf -h "$output_dir/vm_faults" >"$output_dir/vm_faults.readelf.txt"
nm -an "$output_dir/vm_faults" >"$output_dir/vm_faults.symbols.txt"
codegen_arch=$(uname -m)
case "$codegen_arch" in
  x86_64)
    objdump -drwC -M intel --no-show-raw-insn "$output_dir/vm_faults" \
      >"$output_dir/codegen-full.txt"
    ;;
  aarch64)
    objdump -drwC --no-show-raw-insn "$output_dir/vm_faults" \
      >"$output_dir/codegen-full.txt"
    ;;
  *)
    echo "generated-code gate supports only x86_64 and aarch64" >&2
    exit 2
    ;;
esac
awk '/<touch_read_pages>:/ { capture = 1 } capture { print } capture && /^$/ { exit }' \
  "$output_dir/codegen-full.txt" >"$output_dir/codegen-read.txt"
awk '/<touch_write_pages>:/ { capture = 1 } capture { print } capture && /^$/ { exit }' \
  "$output_dir/codegen-full.txt" >"$output_dir/codegen-write.txt"
rg -q '<touch_read_pages>:' "$output_dir/codegen-read.txt"
rg -q '<touch_write_pages>:' "$output_dir/codegen-write.txt"
if [[ $codegen_arch == x86_64 ]]; then
  rg -q 'movzx[[:space:]].*BYTE PTR \[' "$output_dir/codegen-read.txt"
  rg -q 'mov[[:space:]]+BYTE PTR \[[^]]+\],[[:space:]]*[[:alnum:]]+' \
    "$output_dir/codegen-write.txt"
else
  rg -q '\bldrb\b' "$output_dir/codegen-read.txt"
  rg -q '\bstrb\b' "$output_dir/codegen-write.txt"
fi
gzip -9 "$output_dir/codegen-full.txt"

{
  printf 'host_alias=%s\n' "$host_alias"
  printf 'resolved_hostname=%s\n' "$(hostname -f)"
  printf 'utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  printf 'uname='; uname -a
  printf 'page_size='; getconf PAGESIZE
  printf 'online_cpus='; getconf _NPROCESSORS_ONLN
  printf '\nlscpu\n'; lscpu
  printf '\ncpu_model_fields\n'; rg -m 24 '^(model name|vendor_id|Hardware|CPU implementer|CPU architecture|CPU part|Features)' /proc/cpuinfo
  printf '\nnuma_balancing\n'; awk '1' /proc/sys/kernel/numa_balancing
  printf '\nnuma_nodes\n'; lscpu | rg '^NUMA'
  printf '\nmemory\n'; rg '^(MemTotal|MemAvailable|SwapTotal|SwapFree):' /proc/meminfo
  printf '\nthp_enabled\n'; awk '1' /sys/kernel/mm/transparent_hugepage/enabled
  printf '\nthp_defrag\n'; awk '1' /sys/kernel/mm/transparent_hugepage/defrag
  printf '\nrustc\n'; rustc -Vv
  printf '\ncargo\n'; cargo -V
  printf '\ncc\n'; cc --version
  printf '\nclang\n'
  if command -v clang >/dev/null 2>&1; then
    clang --version
  else
    printf 'unavailable: command not installed\n'
  fi
  printf '\nobjdump\n'; objdump --version
  printf '\nnative_target_cfg\n'; rustc -C target-cpu=native --print cfg
  printf '\nfile_dir_mount\n'; findmnt -T "$file_dir" -o TARGET,SOURCE,FSTYPE,OPTIONS
  printf '\nfile_dir_statfs\n'; stat -f "$file_dir"
  printf '\nenvironment_flags\n'
  environment_flags=$(env | rg '^(CARGO_BUILD_TARGET|CARGO_ENCODED_RUSTFLAGS|CFLAGS|CPPFLAGS|CXXFLAGS|RUSTC_WORKSPACE_WRAPPER|RUSTC_WRAPPER|RUSTDOCFLAGS|RUSTFLAGS)=' | sort || true)
  if [[ -n $environment_flags ]]; then
    printf '%s\n' "$environment_flags"
  else
    printf 'none\n'
  fi
} >"$output_dir/host-env.txt"

{
  printf 'source_commit=%s\n' "$source_commit"
  printf 'source_archive_embedded_commit=%s\n' "$archive_commit"
  printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
  printf 'executing_driver_sha256=%s\n' "$running_driver_sha"
  printf 'archived_driver_sha256=%s\n' "$archived_driver_sha"
  printf 'host_alias=%s\n' "$host_alias"
  printf 'resolved_hostname=%s\n' "$(hostname -f)"
  printf 'cpu=%s\n' "$cpu"
  printf 'blocks=%s\n' "$blocks"
  printf 'mib=%s\n' "$mib"
  printf 'file_dir=%s\n' "$file_dir"
  printf 'file_fstype=%s\n' "$file_fstype"
  printf 'c_flags=%s\n' "${c_flags[*]}"
  printf 'rustflags=%s\n' "$RUSTFLAGS"
} >"$output_dir/run-manifest.txt"

printf '%s\n' 'run_id,mode,mib,page_size,pages,setup_ns,touch_ns,minflt,majflt,resident_before,resident_after,checksum,fadvise_rc,cold_verified,external_wall_ns' \
  >"$output_dir/raw.csv"
printf 'SESSION_START host_alias=%s source_commit=%s source_archive_sha256=%s cpu=%s blocks=%s mib=%s\n' \
  "$host_alias" "$source_commit" "$source_archive_sha256" "$cpu" "$blocks" "$mib" \
  >"$output_dir/processes.txt"

# This copy of the schedule is deliberately independent of the copies in
# summarize.py and balanced_schedule(); the three-way agreement check below
# keeps the validator an independent oracle while failing fast on drift.
orders=(
  'anon-first anon-refault file-warm file-cold'
  'anon-refault file-warm file-cold anon-first'
  'file-warm file-cold anon-first anon-refault'
  'file-cold anon-first anon-refault file-warm'
  'file-cold file-warm anon-refault anon-first'
  'anon-first file-cold file-warm anon-refault'
  'anon-refault anon-first file-cold file-warm'
  'file-warm anon-refault anon-first file-cold'
)

shell_schedule=$(printf 'SCHEDULE %s\n' "${orders[@]}")
rust_schedule=$(awk '/^SCHEDULE /' "$output_dir/example-check.log")
python_schedule=$(python3 "$script_dir/summarize.py" --print-schedule)
if [[ $rust_schedule != "$shell_schedule" || $python_schedule != "$shell_schedule" ]]; then
  echo "schedule copies disagree across runner, validator, and Rust contract" >&2
  exit 2
fi

for (( block = 1; block <= blocks; block++ )); do
  read -r -a modes <<<"${orders[$((block - 1))]}"
  for position in 1 2 3 4; do
    mode=${modes[$((position - 1))]}
    run_id=$(printf 'b%02d-p%d' "$block" "$position")
    printf 'PROCESS_START run_id=%s block=%s position=%s mode=%s\n' \
      "$run_id" "$block" "$position" "$mode" >>"$output_dir/processes.txt"
    row=$(python3 "$script_dir/run_one.py" "$output_dir/vm_faults" \
      "$file_dir" "$cpu" "$mode" "$mib" "$run_id")
    external_wall_ns=${row##*,}
    printf '%s\n' "$row" >>"$output_dir/raw.csv"
    printf 'PROCESS_END run_id=%s external_wall_ns=%s\n' \
      "$run_id" "$external_wall_ns" >>"$output_dir/processes.txt"
  done
done
printf 'SESSION_END processes=%s\n' "$((blocks * 4))" >>"$output_dir/processes.txt"

python3 "$script_dir/summarize.py" "$output_dir/raw.csv" >"$output_dir/summary.txt"
sha256sum -c "$output_dir/source-files.sha256" >"$output_dir/source-files-verify.log"
checksums_tmp=$(mktemp)
(
  cd -- "$output_dir"
  rg --files -uu -0 . | sort -z | xargs -0 sha256sum >"$checksums_tmp"
)
mv -- "$checksums_tmp" "$output_dir/SHA256SUMS"

printf 'evidence_dir=%s\n' "$output_dir"
awk '1' "$output_dir/summary.txt"
