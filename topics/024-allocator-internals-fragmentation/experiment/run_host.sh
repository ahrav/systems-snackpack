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
topic=topics/024-allocator-internals-fragmentation

: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the transferred Git archive}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the sender archive digest}"
: "${SOURCE_TREE_MANIFEST_SHA256:?set SOURCE_TREE_MANIFEST_SHA256 to the sender manifest digest}"

# Resolve a relative archive path against the caller's directory now; after
# the cd into the repository below it would name the wrong location.
SOURCE_ARCHIVE_PATH=$(cd "$(dirname -- "$SOURCE_ARCHIVE_PATH")" && pwd -P)/$(basename -- "$SOURCE_ARCHIVE_PATH")

# Python bytecode caches written during validation would dirty the source
# tree between the before and after manifests.
export PYTHONDONTWRITEBYTECODE=1

if [[ -e $output_directory ]]; then
  printf 'output directory already exists: %s\n' "$output_directory" >&2
  exit 2
fi
mkdir -p "$output_directory"
output_directory=$(cd "$output_directory" && pwd -P)
# A relative output path must not silently resolve under the repository after
# the cd below, and in-tree evidence would corrupt the before/after
# source-tree comparison with its own generated files.
if [[ $output_directory == "$repository_root" || $output_directory == "$repository_root"/* ]]; then
  rmdir "$output_directory" 2>/dev/null || true
  printf 'OUTPUT_DIRECTORY must be outside the repository: %s\n' "$output_directory" >&2
  exit 2
fi
mkdir -p "$output_directory"/{binaries,codegen,correctness,gates,processes}

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
archive_commit=$(git get-tar-commit-id <"$SOURCE_ARCHIVE_PATH")
if [[ $archive_commit != "$source_commit" ]]; then
  printf 'archive commit mismatch: expected %s, observed %s\n' \
    "$source_commit" "$archive_commit" >&2
  exit 2
fi

rg --files --hidden --no-ignore -g '!.git/**' -g '!target/**' -0 | LC_ALL=C sort -z \
  | xargs -0 sha256sum >"$output_directory/source-tree.before.sha256"
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
  printf 'archive_commit=%s\n' "$archive_commit"
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
  printf 'page_size=%s\n' "$(getconf PAGE_SIZE)"
  printf 'glibc=%s\n' "$(getconf GNU_LIBC_VERSION)"
  printf 'thp_enabled=%s\n' "$(</sys/kernel/mm/transparent_hugepage/enabled)"
  printf 'cc_version=%s\n' "$(cc -dumpfullversion -dumpversion)"
  printf 'cc_target=%s\n' "$(cc -dumpmachine)"
  printf 'cc_target_options_begin\n'
  cc -Q --help=target
  printf 'cc_target_options_end\n'
  printf 'cflags=%s\n' '-std=c11 -O2 -g -Wall -Wextra -Werror -fno-omit-frame-pointer -fno-builtin-malloc -fno-builtin-free'
  printf 'binutils=%s\n' "$(ld --version | head -1)"
  lscpu
  awk -F: '/^(vendor_id|model name|cpu family|model|stepping|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision)/ { if (!seen[$1]++) print }' /proc/cpuinfo
  if [[ -r /sys/devices/system/cpu/cpu0/regs/identification/midr_el1 ]]; then
    printf 'MIDR_EL1=%s\n' "$(</sys/devices/system/cpu/cpu0/regs/identification/midr_el1)"
  fi
  rustc -vV
  cargo -V
  rustc -C target-cpu=native --print cfg | rg '^(target_arch|target_feature|target_has_atomic|target_pointer_width)'
  printf 'RUSTFLAGS=%s\n' "${RUSTFLAGS-<unset>}"
  printf 'ambient_GLIBC_TUNABLES=%s\n' "${GLIBC_TUNABLES-<unset>}"
  printf 'ambient_LD_PRELOAD=%s\n' "${LD_PRELOAD-<unset>}"
  printf 'ambient_LD_LIBRARY_PATH=%s\n' "${LD_LIBRARY_PATH-<unset>}"
} >"$output_directory/host.txt"

# Caller overrides must not leak into the gates or any probe process; the
# ambient values are recorded above.
unset CARGO_BUILD_RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_TARGET_DIR CARGO_BUILD_TARGET
unset RUSTC RUSTC_WRAPPER RUSTDOC RUSTDOCFLAGS RUSTFLAGS
unset GLIBC_TUNABLES LD_PRELOAD LD_LIBRARY_PATH LD_AUDIT
# Compiler search-path overrides would let cc consume unrecorded headers,
# subprograms, or libraries.
unset CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH COMPILER_PATH GCC_EXEC_PREFIX LIBRARY_PATH
# Replacement modules on the Python import path could bias both summary
# generation and receipt validation.
unset PYTHONPATH PYTHONHOME PYTHONSTARTUP
# Cargo merges $HOME/.cargo and ancestor .cargo configuration into the gate
# commands even with the explicit variables cleared; refuse ancestor configs
# and give the gates a fresh CARGO_HOME.
config_dir=$repository_root
while :; do
  for config_name in config.toml config; do
    if [[ -f "$config_dir/.cargo/$config_name" ]]; then
      printf 'unrecorded Cargo configuration: %s\n' "$config_dir/.cargo/$config_name" >&2
      exit 2
    fi
  done
  if [[ $config_dir == / ]]; then
    break
  fi
  config_dir=$(dirname "$config_dir")
done
export CARGO_HOME="$repository_root/../cargo-home"
mkdir -p "$CARGO_HOME"

rg --files --hidden --no-ignore -g '!.git/**' -0 "$topic" | LC_ALL=C sort -z \
  | xargs -0 sha256sum >"$output_directory/source-files.sha256"

printf 'not applicable: extracted Git archive has no index\n' \
  >"$output_directory/gates/git-diff-check.log"
cargo fmt --all -- --check >"$output_directory/gates/cargo-fmt.log" 2>&1
cargo test --workspace --lib --examples >"$output_directory/gates/cargo-test-lib-examples.log" 2>&1
cargo test --workspace --doc >"$output_directory/gates/cargo-test-doc.log" 2>&1
cargo clippy --workspace --all-targets -- -D warnings >"$output_directory/gates/cargo-clippy.log" 2>&1
cargo bench --workspace --no-run >"$output_directory/gates/cargo-bench-no-run.log" 2>&1
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps \
  >"$output_directory/gates/cargo-doc.log" 2>&1
PYTHONPYCACHEPREFIX="$repository_root/../pycache" \
  python3 -m py_compile \
    "$topic/experiment/run_processes.py" \
    "$topic/experiment/validate_receipts.py"
bash -n "$topic/experiment/run_host.sh"

native_output="$repository_root/../native-output"
mkdir -p "$native_output"
binary="$native_output/allocator_frag_probe"
cc -std=c11 -O2 -g -Wall -Wextra -Werror -fno-omit-frame-pointer \
  -fno-builtin-malloc -fno-builtin-free \
  "$topic/experiment/allocator_frag_probe.c" -o "$binary" \
  >"$output_directory/build.log" 2>&1
# Retain the measured binary inside the bundle with a bundle-relative
# receipt, so the receipt is verifiable without the build host.
cp "$binary" "$output_directory/binaries/allocator_frag_probe"
(
  cd "$output_directory"
  sha256sum binaries/allocator_frag_probe >binary.sha256
)

for replicate in 1 2 3 4; do
  taskset --cpu-list "$cpu" "$binary" compact A "$replicate" 1 262144 256
  taskset --cpu-list "$cpu" "$binary" scattered B "$replicate" 2 262144 256
done >"$output_directory/correctness/replicates.ndjson"

{
  file "$binary"
  readelf -h -d -Ws "$binary"
  nm -D "$binary"
  ldd "$binary"
} >"$output_directory/codegen/elf.txt"
objdump -drwC "$binary" >"$output_directory/codegen/final-binary.txt"
rg -n -A 260 '<main>' "$output_directory/codegen/final-binary.txt" \
  >"$output_directory/codegen/main.txt"
gzip -9 "$output_directory/codegen/final-binary.txt"

python3 "$topic/experiment/run_processes.py" \
  "$binary" "$output_directory/processes" "$cpu" \
  >"$output_directory/process-driver.log"
python3 "$topic/experiment/validate_receipts.py" "$output_directory/processes" \
  >"$output_directory/receipt-validation.txt"

rg --files --hidden --no-ignore -g '!.git/**' -g '!target/**' -0 | LC_ALL=C sort -z \
  | xargs -0 sha256sum >"$output_directory/source-tree.after.sha256"
cmp "$output_directory/source-tree.before.sha256" "$output_directory/source-tree.after.sha256"

{
  printf 'Each treatment application is a fresh process pinned to CPU %s.\n' "$cpu"
  printf 'Each process allocates and touches 262,144 blocks of 256 requested bytes.\n'
  printf 'Each process retains 16,384 blocks and 4,194,304 requested bytes.\n'
  printf 'The primary estimand is scattered/compact post-trim RSS across 12 four-process blocks.\n'
  printf 'The interval covers block-to-block variation in this run window only.\n'
  printf 'Four compact/compact A/A blocks diagnose label and period effects.\n'
  printf 'Allocation, free, and trim clocks exclude adjacent procfs snapshots.\n'
  printf 'The run does not cover multiple arenas, multiple threads, cross-thread frees, or other allocators.\n'
} >"$output_directory/measurement-boundary.txt"

run_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
printf 'run_finished_utc=%s\n' "$run_finished_utc" >>"$output_directory/host.txt"
(
  cd "$output_directory"
  rg --files --hidden --no-ignore -g '!evidence.sha256' -g '!evidence-verification.txt' -0 \
    | LC_ALL=C sort -z | xargs -0 sha256sum >evidence.sha256
  # The reports state that evidence-hash validation passed; retain the proof.
  sha256sum --check --quiet evidence.sha256 >evidence-verification.txt 2>&1
  printf 'evidence manifest verified\n' >>evidence-verification.txt
)
