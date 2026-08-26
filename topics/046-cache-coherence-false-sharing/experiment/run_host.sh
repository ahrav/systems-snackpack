#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
unset BASH_ENV CDPATH ENV GLOBIGNORE LD_PRELOAD PYTHONHOME PYTHONPATH

if [[ $# -ne 7 ]]; then
    printf 'usage: %s OUTPUT_DIR CPU0 CPU1 ITERATIONS BLOCKS AA_BLOCKS SEED\n' "$0" >&2
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 46 host receipts require Linux\n' >&2
    exit 2
fi
: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the source archive digest}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to the authorized target label}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the resolved hostname}"

output_dir=$(realpath -m -- "$1")
cpu0=$2
cpu1=$3
iterations=$4
blocks=$5
aa_blocks=$6
seed=$7
SOURCE_COMMIT=${SOURCE_COMMIT,,}
SOURCE_ARCHIVE_SHA256=${SOURCE_ARCHIVE_SHA256,,}

if [[ ! $SOURCE_COMMIT =~ ^[0-9a-f]{40}$ || ! $SOURCE_ARCHIVE_SHA256 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'source commit or archive digest has the wrong shape\n' >&2
    exit 2
fi
if [[ ! -f $SOURCE_ARCHIVE_PATH ]]; then
    printf 'source archive is not a regular file\n' >&2
    exit 2
fi
source_archive=$(realpath -- "$SOURCE_ARCHIVE_PATH")
actual_archive_sha256=$(sha256sum -- "$source_archive" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$SOURCE_ARCHIVE_SHA256" ]]; then
    printf 'source archive digest mismatch\n' >&2
    exit 2
fi
python3 -I -B - "$source_archive" "$SOURCE_COMMIT" <<'PY'
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive.getmembers():
        # git archive publishes the commit as a global PAX header; tarfile
        # surfaces it only when a real length-delimited PAX record declared it.
        declared = member.pax_headers.get("comment")
        if declared is not None:
            break
    else:
        raise SystemExit("source archive declares no PAX comment header")
if declared != sys.argv[2]:
    raise SystemExit(f"source archive does not embed commit {sys.argv[2]}")
PY
if [[ ! $cpu0 =~ ^[0-9]+$ || ! $cpu1 =~ ^[0-9]+$ || $cpu0 == "$cpu1" ]]; then
    printf 'CPU identifiers must be distinct nonnegative integers\n' >&2
    exit 2
fi
if [[ ! $iterations =~ ^[1-9][0-9]*$ || ! $blocks =~ ^[1-9][0-9]*$ || ! $aa_blocks =~ ^[1-9][0-9]*$ || ! $seed =~ ^[1-9][0-9]*$ ]]; then
    printf 'iterations, blocks, A/A blocks, and seed must be positive integers\n' >&2
    exit 2
fi
if (( blocks < 2 || blocks % 2 != 0 || aa_blocks < 2 || aa_blocks % 2 != 0 )); then
    printf 'publication block counts must be even and at least two\n' >&2
    exit 2
fi
if [[ $iterations -ne 10000000 || $blocks -ne 8 || $aa_blocks -ne 4 || $seed -ne 20260825 || $cpu0 -ne 0 || $cpu1 -ne 1 ]]; then
    printf 'invocation violates the fixed Topic 46 publication contract (rounds/01.md): CPUs 0 and 1, 10000000 iterations per worker, eight primary and four A/A blocks, seed 20260825\n' >&2
    exit 2
fi

runtime_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $runtime_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    printf 'runtime hostname differs from the resolved target\n' >&2
    exit 2
fi
case $SSH_TARGET_LABEL in
    xxl)
        [[ $architecture == x86_64 ]] || { printf 'xxl is not x86-64\n' >&2; exit 2; }
        ;;
    dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
        [[ $architecture == aarch64 || $architecture == arm64 ]] || {
            printf 'authorized Arm target is not AArch64\n' >&2
            exit 2
        }
        ;;
    *)
        printf 'unauthorized Topic 46 target: %s\n' "$SSH_TARGET_LABEL" >&2
        exit 2
        ;;
esac
if [[ -e $output_dir ]]; then
    printf 'output path already exists: %s\n' "$output_dir" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
case $output_dir in
    "$repo_root" | "$repo_root"/*)
        printf 'write host receipts outside the repository\n' >&2
        exit 2
        ;;
esac

python3 -I -B - "$cpu0" "$cpu1" <<'PY'
import os
import pathlib
import sys

cpus = [int(sys.argv[1]), int(sys.argv[2])]
allowed = os.sched_getaffinity(0)
if any(cpu not in allowed for cpu in cpus):
    raise SystemExit(f"requested CPUs {cpus} not contained in allowed set {sorted(allowed)}")

def read(cpu, name):
    return pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/{name}").read_text().strip()

core_ids = [read(cpu, "core_id") for cpu in cpus]
packages = [read(cpu, "physical_package_id") for cpu in cpus]
siblings = set()
for part in read(cpus[0], "thread_siblings_list").split(","):
    if "-" in part:
        first, last = map(int, part.split("-", 1))
        siblings.update(range(first, last + 1))
    else:
        siblings.add(int(part))
if core_ids[0] == core_ids[1] or cpus[1] in siblings:
    raise SystemExit("requested CPUs are simultaneous threads of one physical core")
if packages[0] != packages[1]:
    raise SystemExit("publication pair must remain within one physical package")

line_files = list(pathlib.Path(f"/sys/devices/system/cpu/cpu{cpus[0]}/cache").glob("index*/coherency_line_size"))
line_sizes = {int(path.read_text()) for path in line_files}
if not line_files or line_sizes != {64}:
    raise SystemExit(f"publication requires observed 64-byte sysfs coherence lines, got {sorted(line_sizes)}")
PY

mkdir -p -- "$output_dir"
install -m 0400 -- "$source_archive" "$output_dir/source-archive.tar.gz"
source_tree=$(mktemp -d)
private=$(mktemp -d)
validation_tmp="$output_dir/.receipt-validation.json.tmp"
trap 'rm -rf -- "$source_tree" "$private"; rm -f -- "$validation_tmp"' EXIT

python3 -I -B - "$output_dir/source-archive.tar.gz" <<'PY'
import pathlib
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    roots = set()
    names = set()
    for member in archive.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if member.name in names or path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe or duplicate archive member: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise SystemExit(f"unsupported archive member: {member.name}")
        names.add(member.name)
        if path.parts:
            roots.add(path.parts[0])
    if len(roots) != 1:
        raise SystemExit("source archive must have one top-level root")
PY
tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_tree"
runner_relative=topics/046-cache-coherence-false-sharing/experiment/run_host.sh
mapfile -t archived_runners < <(
    rg --files --hidden --no-ignore "$source_tree" | rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 46 host runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/046-cache-coherence-false-sharing/experiment"
if ! cmp -s -- "${BASH_SOURCE[0]}" "$archive_script_dir/run_host.sh"; then
    printf 'executing host runner differs from archived runner\n' >&2
    exit 2
fi

write_source_manifest() {
    local destination=$1
    (
        cd -- "$archive_repo_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum --
    ) >"$destination"
}
write_source_manifest "$output_dir/source-manifest-before.sha256"

{
    printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'source_commit=%s\n' "$SOURCE_COMMIT"
    printf 'source_archive_sha256=%s\n' "$SOURCE_ARCHIVE_SHA256"
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'runtime_hostname=%s\n' "$runtime_hostname"
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel_release=%s\n' "$(uname -r)"
    printf 'cpu0=%s\n' "$cpu0"
    printf 'cpu1=%s\n' "$cpu1"
    printf 'iterations_per_thread=%s\n' "$iterations"
    printf 'blocks=%s\n' "$blocks"
    printf 'aa_blocks=%s\n' "$aa_blocks"
    printf 'seed=%s\n' "$seed"
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'allowed_affinity=%s\n' "$(taskset --pid --cpu-list $$)"
    printf 'cpu0_core_id=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu0}/topology/core_id")"
    printf 'cpu1_core_id=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu1}/topology/core_id")"
    printf 'cpu0_package_id=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu0}/topology/physical_package_id")"
    printf 'cpu1_package_id=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu1}/topology/physical_package_id")"
    printf 'cpu0_thread_siblings=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu0}/topology/thread_siblings_list")"
    printf 'cpu1_thread_siblings=%s\n' "$(<"/sys/devices/system/cpu/cpu${cpu1}/topology/thread_siblings_list")"
    printf 'perf_event_paranoid=%s\n' "$(</proc/sys/kernel/perf_event_paranoid)"
    printf 'build_flags=RUSTFLAGS=-C target-cpu=native cargo build --locked --offline --release --example cache_coherence_probe\n'
    printf 'coherence_line_sizes='
    for line_file in /sys/devices/system/cpu/cpu"${cpu0}"/cache/index*/coherency_line_size; do
        printf '%s:%s ' "$line_file" "$(<"$line_file")"
    done
    printf '\n'
    uname -a
    lscpu
    lscpu -e=CPU,NODE,SOCKET,CORE,CACHE,ONLINE
    rustc -Vv
    cargo -Vv
    gcc --version
    python3 --version
    objdump --version
    perf version
    rustc -C target-cpu=native --print cfg
    rustc --print target-features
} >"$output_dir/host.txt" 2>&1

set +e
perf c2c record -e list >"$output_dir/perf-c2c-support.txt" 2>&1
perf_c2c_status=$?
set -e
printf 'exit_status=%s\n' "$perf_c2c_status" >>"$output_dir/perf-c2c-support.txt"

(
    cd -- "$archive_repo_root"
    CARGO_TARGET_DIR="$private/cargo-target" cargo test --locked --offline \
        --package cache-coherence-false-sharing --lib --examples
    CARGO_TARGET_DIR="$private/cargo-target" cargo test --locked --offline \
        --package cache-coherence-false-sharing --doc
    printf 'CORRECTNESS_STATUS=pass\n'
) >"$output_dir/correctness.txt" 2>&1

(
    cd -- "$archive_repo_root"
    printf 'COMMAND=RUSTFLAGS=-C target-cpu=native cargo build --locked --offline --release --example cache_coherence_probe\n'
    CARGO_TARGET_DIR="$private/cargo-target" RUSTFLAGS='-C target-cpu=native' \
        cargo build --locked --offline --release \
        --package cache-coherence-false-sharing --example cache_coherence_probe
    printf 'BUILD_STATUS=pass\n'
) >"$output_dir/build.txt" 2>&1

mkdir -- "$output_dir/binary"
install -m 0500 -- "$private/cargo-target/release/examples/cache_coherence_probe" \
    "$output_dir/binary/cache_coherence_probe"
binary="$output_dir/binary/cache_coherence_probe"
sha256sum -- "$binary" >"$output_dir/binary.sha256"
"$binary" packed 100000 "$cpu0" "$cpu1" >"$output_dir/smoke-packed.json"
"$binary" padded 100000 "$cpu0" "$cpu1" >"$output_dir/smoke-padded.json"

objdump -d -C --no-show-raw-insn "$binary" >"$output_dir/codegen.txt"
rg -n -A 80 -B 2 '<topic46_increment>:' "$output_dir/codegen.txt" \
    >"$output_dir/codegen-increment.txt"
case $architecture in
    x86_64)
        rg -q '\block\b.*\b(inc|add|xadd)' "$output_dir/codegen-increment.txt"
        ;;
    aarch64 | arm64)
        rg -q '\b(ldadd|ldxr|ldaxr|stxr|stlxr|__aarch64_ldadd)' \
            "$output_dir/codegen-increment.txt"
        ;;
esac
printf 'status=PASS architecture=%s\n' "$architecture" >"$output_dir/codegen-check.txt"

python3 -I -B "$archive_script_dir/run_processes.py" \
    --binary "$binary" --out "$output_dir/experiment" \
    --iterations "$iterations" --cpu0 "$cpu0" --cpu1 "$cpu1" \
    --blocks "$blocks" --aa-blocks "$aa_blocks" --seed "$seed" \
    >"$output_dir/run-processes.txt" 2>&1

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff"

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-label "$SSH_TARGET_LABEL" \
    --expected-resolved-host "$SSH_RESOLVED_HOSTNAME" \
    --expected-source-commit "$SOURCE_COMMIT" \
    --expected-archive-sha256 "$SOURCE_ARCHIVE_SHA256" \
    --expected-architecture "$architecture" --expected-blocks "$blocks" \
    --expected-aa-blocks "$aa_blocks" --output "$validation_tmp"

write_source_manifest "$private/source-manifest-final.sha256"
cmp -s "$output_dir/source-manifest-before.sha256" "$private/source-manifest-final.sha256"
final_binary_sha256=$(sha256sum -- "$binary" | awk '{print $1}')
initial_binary_sha256=$(awk '{print $1}' "$output_dir/binary.sha256")
if [[ $final_binary_sha256 != "$initial_binary_sha256" ]]; then
    printf 'binary changed during host gates\n' >&2
    exit 2
fi
mv -- "$validation_tmp" "$output_dir/receipt-validation.json"
printf 'status=PASS\n' >"$output_dir/status.txt"
