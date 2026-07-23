#!/usr/bin/env bash
set -euo pipefail

if (( $# < 4 || $# > 6 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [CPU] [BLOCKS]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
cpu=${5:-0}
blocks=${6:-12}

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
if [[ $output_dir != /* ]]; then
  echo "OUTPUT_DIR must be absolute" >&2
  exit 2
fi
if [[ $cpu != 0 || $blocks != 12 ]]; then
  echo "recorded runs require CPU 0 and twelve blocks" >&2
  exit 2
fi
if [[ -z ${SOURCE_ARCHIVE:-} || $SOURCE_ARCHIVE != /* || ! -f $SOURCE_ARCHIVE ]]; then
  echo "SOURCE_ARCHIVE must name an absolute, readable git archive" >&2
  exit 2
fi

for required_tool in \
  awk cargo cc cp date dirname env getconf git gzip hostname lscpu mkdir mktemp mv nm \
  objdump python3 readelf rg rustc sha256sum sort stat tar taskset wc xargs; do
  if ! command -v "$required_tool" >/dev/null 2>&1; then
    echo "required tool is unavailable: $required_tool" >&2
    exit 2
  fi
done
for required_path in \
  /proc/cpuinfo \
  /proc/meminfo \
  /proc/self/pagemap \
  /proc/sys/kernel/randomize_va_space \
  /sys/kernel/mm/transparent_hugepage/enabled \
  /sys/devices/system/cpu/cpu0/cache; do
  if [[ ! -r $required_path ]]; then
    echo "required host evidence is unreadable: $required_path" >&2
    exit 2
  fi
done
if ! taskset --cpu-list "$cpu" true; then
  echo "CPU $cpu is unavailable to the current affinity mask" >&2
  exit 2
fi
page_size=$(getconf PAGESIZE)
if [[ $page_size != 4096 ]]; then
  echo "recorded page-offset fields require a 4096-byte base page" >&2
  exit 2
fi
mapfile -t cache_line_files < <(
  rg --files -uu -L /sys/devices/system/cpu/cpu0/cache \
    | rg '/coherency_line_size$' | sort
)
data_cache_count=0
for cache_line_file in "${cache_line_files[@]}"; do
  cache_index_dir=$(dirname -- "$cache_line_file")
  cache_type_file="$cache_index_dir/type"
  if [[ ! -r $cache_type_file ]]; then
    echo "cache index lacks a readable type field: $cache_index_dir" >&2
    exit 2
  fi
  cache_type=$(awk 'NR == 1 { print; exit }' "$cache_type_file")
  case "$cache_type" in
    Data|Unified)
      data_cache_count=$((data_cache_count + 1))
      cache_line_size=$(awk 'NR == 1 { print; exit }' "$cache_line_file")
      if [[ $cache_line_size != 64 ]]; then
        echo "$cache_type cache at $cache_index_dir has $cache_line_size-byte lines; recorded runs require 64" >&2
        exit 2
      fi
      ;;
  esac
done
if (( data_cache_count == 0 )); then
  echo "cpu0 cache sysfs exposes no data or unified cache" >&2
  exit 2
fi

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
topic_root="$repo_root/topics/013-cache-aware-oblivious"
script_dir="$topic_root/experiment"
archived_driver="$script_dir/run_processes.sh"
for required_file in \
  "$archived_driver" \
  "$script_dir/run_schedule.py" \
  "$script_dir/summarize.py" \
  "$script_dir/pagemap_probe.py" \
  "$topic_root/benches/cache_layout.rs" \
  "$topic_root/examples/check_contracts.rs" \
  "$topic_root/src/lib.rs"; do
  if [[ ! -r $required_file ]]; then
    echo "verified archive lacks required Topic 13 source: $required_file" >&2
    exit 2
  fi
done

case ${TOPIC13_ARCHIVED_STAGE:-} in
  '')
    child_status=0
    env TOPIC13_ARCHIVED_STAGE=1 SOURCE_ARCHIVE="$archive_gz" \
      "$archived_driver" "$@" || child_status=$?
    exit "$child_status"
    ;;
  1)
    running_driver_sha=$(sha256sum "${BASH_SOURCE[0]}" | awk '{print $1}')
    archived_driver_sha=$(sha256sum "$archived_driver" | awk '{print $1}')
    if [[ $running_driver_sha != "$archived_driver_sha" ]]; then
      echo "executing driver differs from the verified source archive" >&2
      exit 2
    fi
    ;;
  *)
    echo "invalid internal archive stage" >&2
    exit 2
    ;;
esac

if [[ -d $output_dir ]]; then
  shopt -s nullglob dotglob
  existing_entries=("$output_dir"/*)
  shopt -u nullglob dotglob
  if (( ${#existing_entries[@]} != 0 )); then
    echo "OUTPUT_DIR must be absent or empty" >&2
    exit 2
  fi
fi
mkdir -p -- "$output_dir/gates"
output_dir=$(cd -- "$output_dir" && pwd)
cd -- "$repo_root"

rg --files -uu -0 \
  Cargo.toml Cargo.lock rust-toolchain.toml topics/013-cache-aware-oblivious \
  | sort -z | xargs -0 sha256sum >"$output_dir/source-files.sha256"

# A git archive has no index. A temporary index recreates the whitespace check
# against the exact extracted files without relying on the caller's worktree.
git init -q
git add --all
git diff --cached --check >"$output_dir/gates/git-diff-check.log" 2>&1

unset CARGO_BUILD_TARGET CARGO_ENCODED_RUSTFLAGS RUSTC_WORKSPACE_WRAPPER RUSTC_WRAPPER
export CARGO_TARGET_DIR="$repo_root/target"
export TOPIC13_SOURCE_COMMIT="$source_commit"
export RUSTFLAGS="-C target-cpu=native -C debuginfo=1 -C codegen-units=1"

cargo fmt --all -- --check >"$output_dir/gates/cargo-fmt.log" 2>&1
cargo test --locked --workspace --lib --examples \
  >"$output_dir/gates/cargo-test-lib-examples.log" 2>&1
cargo test --locked --workspace --doc >"$output_dir/gates/cargo-test-doc.log" 2>&1
cargo clippy --locked --workspace --all-targets -- -D warnings \
  >"$output_dir/gates/cargo-clippy.log" 2>&1
cargo bench --locked --workspace --no-run \
  >"$output_dir/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS="-D warnings" cargo doc --locked --workspace --no-deps \
  >"$output_dir/gates/cargo-doc.log" 2>&1

cargo run --locked -p systems-snackpack-topic-013 --example check_contracts \
  >"$output_dir/example-check.log" 2>&1
cargo build --locked --release -p systems-snackpack-topic-013 --bench cache_layout \
  >"$output_dir/gates/cargo-build-benchmark.log" 2>&1

mapfile -t benchmark_candidates < <(
  rg --files target/release/deps | rg '/cache_layout-[0-9a-f]+$' | sort
)
if (( ${#benchmark_candidates[@]} != 1 )); then
  echo "expected one cache_layout benchmark executable, observed ${#benchmark_candidates[@]}" >&2
  exit 2
fi
benchmark_binary=${benchmark_candidates[0]}
if [[ ! -x $benchmark_binary ]]; then
  echo "cache_layout benchmark artifact is not executable" >&2
  exit 2
fi
cp -- "$benchmark_binary" "$output_dir/cache_layout-bench"
(cd -- "$output_dir" && sha256sum cache_layout-bench >cache_layout-bench.sha256)
readelf -h "$output_dir/cache_layout-bench" >"$output_dir/cache_layout-bench.readelf.txt"
nm -anC "$output_dir/cache_layout-bench" >"$output_dir/cache_layout-bench.symbols.txt"

codegen_arch=$(uname -m)
case "$codegen_arch" in
  x86_64)
    objdump -drwC -M intel --no-show-raw-insn "$output_dir/cache_layout-bench" \
      >"$output_dir/codegen-full.txt"
    ;;
  aarch64)
    objdump -drwC --no-show-raw-insn "$output_dir/cache_layout-bench" \
      >"$output_dir/codegen-full.txt"
    ;;
  *)
    echo "generated-code gate supports only x86_64 and aarch64" >&2
    exit 2
    ;;
esac
for symbol in transpose_naive transpose_tiled transpose_recursive; do
  awk -v pattern="<systems_snackpack_topic_013::${symbol}" \
    'index($0, pattern) && $0 ~ /^[[:xdigit:]]+[[:space:]]+</ { capture = 1 }
     capture { print }
     capture && /^$/ { exit }' \
    "$output_dir/codegen-full.txt" >"$output_dir/codegen-${symbol}.txt"
  if ! rg -q "^[[:xdigit:]]+[[:space:]]+<systems_snackpack_topic_013::${symbol}" \
    "$output_dir/codegen-${symbol}.txt"; then
    echo "generated code does not contain $symbol" >&2
    exit 2
  fi
done
gzip -9 "$output_dir/codegen-full.txt"

mapfile -t cache_evidence_files < <(
  rg --files -uu -L /sys/devices/system/cpu/cpu0/cache \
    | rg '/(level|type|size|coherency_line_size|number_of_sets|ways_of_associativity|shared_cpu_list)$' \
    | sort
)
if (( ${#cache_evidence_files[@]} == 0 )); then
  echo "cache sysfs probe found no index geometry files" >&2
  exit 2
fi

{
  printf 'host_alias=%s\n' "$host_alias"
  printf 'resolved_hostname=%s\n' "$(hostname -f)"
  printf 'utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
  printf 'uname='; uname -a
  printf 'architecture='; uname -m
  printf 'page_size=%s\n' "$page_size"
  printf 'validated_data_unified_cache_line_bytes=64\n'
  printf 'validated_data_unified_cache_count=%s\n' "$data_cache_count"
  printf 'online_cpus='; getconf _NPROCESSORS_ONLN
  printf 'configured_cpus='; getconf _NPROCESSORS_CONF
  printf 'affinity='; taskset --cpu-list --pid "$$"
  printf '\nlscpu\n'; lscpu
  printf '\ncpu_model_fields\n'
  rg -m 64 \
    '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
    /proc/cpuinfo
  printf '\ncache_sysfs\n'
  while IFS= read -r cache_file; do
    printf '%s=' "$cache_file"
    awk '1' "$cache_file"
  done < <(printf '%s\n' "${cache_evidence_files[@]}")
  printf '\nmemory\n'
  rg '^(MemTotal|MemAvailable|SwapTotal|SwapFree|HugePages_Total|HugePages_Free|Hugepagesize):' \
    /proc/meminfo
  for optional_file in \
    /proc/sys/kernel/numa_balancing \
    /proc/sys/kernel/randomize_va_space \
    /sys/kernel/mm/transparent_hugepage/enabled \
    /sys/kernel/mm/transparent_hugepage/defrag \
    /sys/devices/system/cpu/cpu0/cpufreq/scaling_governor \
    /sys/devices/system/cpu/intel_pstate/no_turbo \
    /sys/devices/system/cpu/cpufreq/boost; do
    if [[ -r $optional_file ]]; then
      printf '\n%s\n' "$optional_file"
      awk '1' "$optional_file"
    fi
  done
  printf '\nrustc\n'; rustc -Vv
  printf '\ncargo\n'; cargo -V
  printf '\ncc\n'; cc --version
  printf '\nobjdump\n'; objdump --version
  printf '\nnative_target_cfg\n'; rustc -C target-cpu=native --print cfg
  printf '\nnative_target_features\n'; rustc -C target-cpu=native --print target-features
  printf '\ncc_native_target_options\n'
  cc -Q --help=target -march=native 2>&1 || true
  printf '\neffective_environment_flags\n'
  environment_flags=$(
    env | rg \
      '^(CARGO_BUILD_TARGET|CARGO_ENCODED_RUSTFLAGS|CARGO_TARGET_DIR|CFLAGS|CPPFLAGS|CXXFLAGS|RUSTC_WORKSPACE_WRAPPER|RUSTC_WRAPPER|RUSTDOCFLAGS|RUSTFLAGS|TOPIC13_SOURCE_COMMIT)=' \
      | sort || true
  )
  if [[ -n $environment_flags ]]; then
    printf '%s\n' "$environment_flags"
  else
    printf 'none\n'
  fi
} >"$output_dir/host-env.txt"

python3 "$script_dir/pagemap_probe.py" >"$output_dir/pagemap-probe.txt"

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
  printf 'processes=%s\n' "$((blocks * 6))"
  printf 'matrix_edge=2048\n'
  printf 'page_size=%s\n' "$page_size"
  printf 'validated_data_unified_cache_line_bytes=64\n'
  printf 'validated_data_unified_cache_count=%s\n' "$data_cache_count"
  printf 'leading_dimensions=2048,2049\n'
  printf 'tile_edge=32\n'
  printf 'recursive_leaf_elements=1024\n'
  printf 'condition_bytes=134217728\n'
  printf 'cargo_target_dir=%s\n' "$CARGO_TARGET_DIR"
  printf 'rustflags=%s\n' "$RUSTFLAGS"
  printf 'embedded_commit_environment=%s\n' "$TOPIC13_SOURCE_COMMIT"
  printf 'benchmark_sha256=%s\n' \
    "$(awk '{print $1}' "$output_dir/cache_layout-bench.sha256")"
} >"$output_dir/run-manifest.txt"

# These independent copies make any schedule drift fail before timing begins.
orders=(
  'pow2-naive pow2-tiled pow2-recursive padded-naive padded-tiled padded-recursive'
  'pow2-tiled pow2-recursive padded-naive padded-tiled padded-recursive pow2-naive'
  'pow2-recursive padded-naive padded-tiled padded-recursive pow2-naive pow2-tiled'
  'padded-naive padded-tiled padded-recursive pow2-naive pow2-tiled pow2-recursive'
  'padded-tiled padded-recursive pow2-naive pow2-tiled pow2-recursive padded-naive'
  'padded-recursive pow2-naive pow2-tiled pow2-recursive padded-naive padded-tiled'
  'padded-recursive padded-tiled padded-naive pow2-recursive pow2-tiled pow2-naive'
  'padded-tiled padded-naive pow2-recursive pow2-tiled pow2-naive padded-recursive'
  'padded-naive pow2-recursive pow2-tiled pow2-naive padded-recursive padded-tiled'
  'pow2-recursive pow2-tiled pow2-naive padded-recursive padded-tiled padded-naive'
  'pow2-tiled pow2-naive padded-recursive padded-tiled padded-naive pow2-recursive'
  'pow2-naive padded-recursive padded-tiled padded-naive pow2-recursive pow2-tiled'
)
shell_schedule=$(printf 'SCHEDULE %s\n' "${orders[@]}")
rust_schedule=$(awk '/^SCHEDULE /' "$output_dir/example-check.log")
runner_schedule=$(python3 "$script_dir/run_schedule.py" --print-schedule)
validator_schedule=$(python3 "$script_dir/summarize.py" --print-schedule)
if [[ $rust_schedule != "$shell_schedule" \
  || $runner_schedule != "$shell_schedule" \
  || $validator_schedule != "$shell_schedule" ]]; then
  echo "schedule copies disagree across shell, Rust, runner, and validator" >&2
  exit 2
fi

python3 "$script_dir/run_schedule.py" \
  "$output_dir/cache_layout-bench" \
  "$output_dir/raw.tsv" \
  "$output_dir/processes.txt" \
  "$source_commit" \
  "$cpu"
python3 "$script_dir/summarize.py" "$output_dir/raw.tsv" "$source_commit" \
  >"$output_dir/summary.txt"

sha256sum -c "$output_dir/source-files.sha256" >"$output_dir/source-files-verify.log"
(cd -- "$output_dir" && sha256sum -c cache_layout-bench.sha256 >cache_layout-bench-verify.log)
checksums_tmp=$(mktemp)
(
  cd -- "$output_dir"
  rg --files -uu -0 . | sort -z | xargs -0 sha256sum >"$checksums_tmp"
)
mv -- "$checksums_tmp" "$output_dir/SHA256SUMS"
checksums_tmp=

printf 'evidence_dir=%s\n' "$output_dir"
awk '1' "$output_dir/summary.txt"
