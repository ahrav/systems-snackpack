#!/usr/bin/env bash
set -euo pipefail

if (( $# < 4 || $# > 6 )); then
  echo "usage: run_processes.sh OUTPUT_DIR HOST_ALIAS SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 [CPU] [PAIRS]" >&2
  exit 2
fi

output_dir=$1
host_alias=$2
source_commit=$3
source_archive_sha256=$4
cpu=${5:-0}
pairs=${6:-12}

if [[ $output_dir != /* ]]; then
  echo "OUTPUT_DIR must be absolute" >&2
  exit 2
fi
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
if [[ ! $cpu =~ ^[0-9]+$ ]]; then
  echo "CPU must be a nonnegative integer" >&2
  exit 2
fi
if [[ $pairs != 12 ]]; then
  echo "recorded runs require twelve AB/BA pairs" >&2
  exit 2
fi
if [[ -z ${SOURCE_ARCHIVE:-} || $SOURCE_ARCHIVE != /* || ! -f $SOURCE_ARCHIVE ]]; then
  echo "SOURCE_ARCHIVE must name an absolute, readable git archive" >&2
  exit 2
fi

for tool in \
  awk cargo cmp cp dirname env git gzip mkdir mktemp mv nm objdump python3 readelf \
  rg rustc sed sha256sum sort tar taskset uname xargs; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "required tool is unavailable: $tool" >&2
    exit 2
  fi
done
if ! taskset --cpu-list "$cpu" true; then
  echo "CPU $cpu is unavailable to the current affinity mask" >&2
  exit 2
fi

archive_gz=$(mktemp)
archive_tar=$(mktemp)
extracted_root=$(mktemp -d)
evidence_manifest_tmp=
cleanup() {
  rm -rf -- "$extracted_root"
  rm -f -- "$archive_gz" "$archive_tar"
  if [[ -n $evidence_manifest_tmp ]]; then
    rm -f -- "$evidence_manifest_tmp"
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
topic_root="$repo_root/topics/014-cpu-dispatch-portable-optimization"
script_root="$topic_root/experiment"
archived_driver="$script_root/run_processes.sh"
for required_file in \
  "$archived_driver" \
  "$script_root/probe_remote.sh" \
  "$script_root/run_schedule.py" \
  "$script_root/summarize.py" \
  "$topic_root/benches/cpu_dispatch.rs" \
  "$topic_root/examples/check_contracts.rs" \
  "$topic_root/src/lib.rs"; do
  if [[ ! -r $required_file ]]; then
    echo "verified archive lacks required Topic 14 source: $required_file" >&2
    exit 2
  fi
done

case ${TOPIC14_ARCHIVED_STAGE:-} in
  '')
    child_status=0
    env TOPIC14_ARCHIVED_STAGE=1 SOURCE_ARCHIVE="$archive_gz" \
      bash "$archived_driver" "$@" || child_status=$?
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
output_dir=$(cd -- "$output_dir" && pwd -P)
repo_root=$(cd -- "$repo_root" && pwd -P)
if [[ $output_dir == "$repo_root" || $output_dir == "$repo_root"/* ]]; then
  echo "OUTPUT_DIR must be outside the extracted source tree" >&2
  exit 2
fi
cd -- "$repo_root"

rg --files -uu -0 \
  Cargo.toml Cargo.lock rust-toolchain.toml topics/014-cpu-dispatch-portable-optimization \
  | sort -z | xargs -0 sha256sum >"$output_dir/source-files.before.sha256"
printf '%s  source-archive.tar.gz\n' "$source_archive_sha256" \
  >"$output_dir/source-archive.sha256"

architecture=$(uname -m)
case "$architecture" in
  x86_64)
    target_cpu=x86-64
    expected_variant=avx2
    ;;
  aarch64)
    target_cpu=generic
    expected_variant=neon
    ;;
  *)
    echo "recorded experiment supports only x86_64 and aarch64" >&2
    exit 2
    ;;
esac

{
  printf 'RUSTFLAGS=-C target-cpu=%s -C debuginfo=1 -C codegen-units=1 -C llvm-args=-vectorize-loops=false -C llvm-args=-vectorize-slp=false\n' "$target_cpu"
  printf 'TOPIC14_SOURCE_COMMIT=%s\n' "$source_commit"
  printf 'architecture=%s\n' "$architecture"
  printf 'expected_variant=%s\n' "$expected_variant"
} >"$output_dir/build-flags.txt"

bash "$script_root/probe_remote.sh" "$host_alias" "$cpu" >"$output_dir/host.txt"
rustc \
  -C "target-cpu=$target_cpu" \
  --print cfg >"$output_dir/rustc-target-cfg.txt"
rustc \
  -C "target-cpu=$target_cpu" \
  --print target-features >"$output_dir/rustc-target-features.txt"

unset CARGO_BUILD_TARGET CARGO_ENCODED_RUSTFLAGS RUSTC_WORKSPACE_WRAPPER RUSTC_WRAPPER
export CARGO_TARGET_DIR="$repo_root/target"
export TOPIC14_SOURCE_COMMIT="$source_commit"
export RUSTFLAGS="-C target-cpu=$target_cpu -C debuginfo=1 -C codegen-units=1 -C llvm-args=-vectorize-loops=false -C llvm-args=-vectorize-slp=false"
export PYTHONDONTWRITEBYTECODE=1

# A git archive has no index. A temporary index recreates the whitespace gate
# against the exact extracted source instead of the caller's worktree.
git init -q
git add --all
git diff --cached --check >"$output_dir/gates/git-diff-check.log" 2>&1

cargo fmt --all -- --check >"$output_dir/gates/cargo-fmt.log" 2>&1
cargo test --locked --workspace --lib --examples \
  >"$output_dir/gates/cargo-test-lib-examples.log" 2>&1
cargo test --locked --workspace --doc \
  >"$output_dir/gates/cargo-test-doc.log" 2>&1
cargo clippy --locked --workspace --all-targets -- -D warnings \
  >"$output_dir/gates/cargo-clippy.log" 2>&1
cargo bench --locked --workspace --no-run \
  >"$output_dir/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS="-D warnings" cargo doc --locked --workspace --no-deps \
  >"$output_dir/gates/cargo-doc.log" 2>&1
cargo run --locked -p systems-snackpack-topic-014 --example check_contracts \
  >"$output_dir/example-check.log" 2>&1
cargo build --locked --release -p systems-snackpack-topic-014 --bench cpu_dispatch \
  >"$output_dir/gates/cargo-build-benchmark.log" 2>&1

mapfile -t benchmark_candidates < <(
  rg --files target/release/deps | rg '/cpu_dispatch-[0-9a-f]+$' | sort
)
if (( ${#benchmark_candidates[@]} != 1 )); then
  echo "expected one cpu_dispatch benchmark executable, observed ${#benchmark_candidates[@]}" >&2
  exit 2
fi
benchmark_binary=${benchmark_candidates[0]}
if [[ ! -x $benchmark_binary ]]; then
  echo "cpu_dispatch benchmark artifact is not executable" >&2
  exit 2
fi
cp -- "$benchmark_binary" "$output_dir/cpu-dispatch-bench"
(cd -- "$output_dir" && sha256sum cpu-dispatch-bench >cpu-dispatch-bench.sha256)
readelf -h "$output_dir/cpu-dispatch-bench" >"$output_dir/cpu-dispatch-bench.readelf.txt"
nm -anC "$output_dir/cpu-dispatch-bench" >"$output_dir/cpu-dispatch-bench.symbols.txt"

case "$architecture" in
  x86_64)
    objdump -drwC -M intel --no-show-raw-insn "$output_dir/cpu-dispatch-bench" \
      >"$output_dir/codegen-full.txt"
    simd_symbol=count_eq_avx2_unchecked
    ;;
  aarch64)
    objdump -drwC --no-show-raw-insn "$output_dir/cpu-dispatch-bench" \
      >"$output_dir/codegen-full.txt"
    simd_symbol=count_eq_neon_unchecked
    ;;
esac
for symbol in count_eq_scalar "$simd_symbol" resolve_best count_eq_dispatch_once; do
  awk -v pattern="$symbol" \
    'index($0, pattern) && $0 ~ /^[[:xdigit:]]+[[:space:]]+</ { capture = 1 }
     capture { print }
     capture && /^$/ { exit }' \
    "$output_dir/codegen-full.txt" >"$output_dir/codegen-${symbol}.txt"
  if ! rg -q "^[[:xdigit:]]+[[:space:]]+<.*${symbol}" \
    "$output_dir/codegen-${symbol}.txt"; then
    echo "generated code does not contain $symbol" >&2
    exit 2
  fi
done
case "$architecture" in
  x86_64)
    if ! rg -q 'vpcmpeqb' "$output_dir/codegen-${simd_symbol}.txt" ||
      ! rg -q 'vpmovmskb' "$output_dir/codegen-${simd_symbol}.txt"; then
      echo "AVX2 kernel lacks the expected compare or mask instruction" >&2
      exit 2
    fi
    if rg -q '(xmm|ymm|zmm)[0-9]+' "$output_dir/codegen-count_eq_scalar.txt"; then
      echo "scalar control contains x86 vector registers" >&2
      exit 2
    fi
    ;;
  aarch64)
    if ! rg -q '[[:space:]]cmeq[[:space:]]' "$output_dir/codegen-${simd_symbol}.txt" ||
      ! rg -q '[[:space:]]addv[[:space:]]' "$output_dir/codegen-${simd_symbol}.txt"; then
      echo "Advanced SIMD kernel lacks the expected compare or horizontal add" >&2
      exit 2
    fi
    if rg -q '[[:space:]]v[0-9]+\.' "$output_dir/codegen-count_eq_scalar.txt"; then
      echo "scalar control contains AArch64 vector registers" >&2
      exit 2
    fi
    ;;
esac
gzip -9 "$output_dir/codegen-full.txt"

python3 "$script_root/run_schedule.py" \
  "$output_dir/cpu-dispatch-bench" \
  "$output_dir/raw.tsv" \
  "$output_dir/process.log" \
  "$source_commit" \
  "$cpu"
python3 "$script_root/summarize.py" "$output_dir/raw.tsv" "$source_commit" \
  >"$output_dir/summary.txt"

observed_variants=$(awk -F '\t' 'NR > 1 && $6 != "scalar_whole" { print $7 }' \
  "$output_dir/raw.tsv" | sort -u)
if [[ $observed_variants != "$expected_variant" ]]; then
  echo "recorded variant $observed_variants differs from expected $expected_variant" >&2
  exit 2
fi
expected_rows=$((1 + 3 * 12 * 2))
observed_rows=$(awk 'END { print NR }' "$output_dir/raw.tsv")
if [[ $observed_rows != "$expected_rows" ]]; then
  echo "raw TSV has $observed_rows rows, expected $expected_rows" >&2
  exit 2
fi

rg --files -uu -0 \
  Cargo.toml Cargo.lock rust-toolchain.toml topics/014-cpu-dispatch-portable-optimization \
  | sort -z | xargs -0 sha256sum >"$output_dir/source-files.after.sha256"
if ! cmp -s \
  "$output_dir/source-files.before.sha256" \
  "$output_dir/source-files.after.sha256"; then
  echo "source files changed while the experiment ran" >&2
  exit 2
fi
cp -- "$output_dir/source-files.after.sha256" "$output_dir/source-files.sha256"

evidence_manifest_tmp=$(mktemp)
(cd -- "$output_dir" && \
  rg --files -uu -0 . | sort -z | xargs -0 sha256sum) >"$evidence_manifest_tmp"
mv -- "$evidence_manifest_tmp" "$output_dir/evidence.sha256"
evidence_manifest_tmp=
printf 'completed_source_commit=%s\n' "$source_commit"
printf 'completed_architecture=%s\n' "$architecture"
printf 'completed_variant=%s\n' "$expected_variant"
printf 'completed_process_rows=%s\n' "$((expected_rows - 1))"
