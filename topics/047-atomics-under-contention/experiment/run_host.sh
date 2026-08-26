#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
unset BASH_ENV CDPATH ENV GLOBIGNORE LD_PRELOAD PYTHONHOME PYTHONPATH
unset CARGO_ENCODED_RUSTFLAGS

if [[ $# -ne 9 ]]; then
    printf 'usage: %s OUTPUT_DIR COORDINATOR_CPU WORKER_CPU_CSV ITERATIONS WARMUP_ITERATIONS BATCH_SIZE BLOCKS AA_BLOCKS SEED\n' "$0" >&2
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 47 host receipts require Linux\n' >&2
    exit 2
fi
: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the source archive digest}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to the authorized target label}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the resolved hostname}"

output_dir=$(realpath -m -- "$1")
coordinator_cpu=$2
worker_cpu_csv=$3
iterations=$4
warmup_iterations=$5
batch_size=$6
blocks=$7
aa_blocks=$8
seed=$9
threads=8
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
source_archive_input=$(realpath -- "$SOURCE_ARCHIVE_PATH")

for value in "$coordinator_cpu" "$iterations" "$warmup_iterations" "$batch_size" "$blocks" "$aa_blocks" "$seed"; do
    if [[ ! $value =~ ^[1-9][0-9]*$ ]]; then
        printf 'numeric publication inputs must be positive integers\n' >&2
        exit 2
    fi
done
if [[ $coordinator_cpu -ne 8 || $worker_cpu_csv != 0,1,2,3,4,5,6,7 \
    || $iterations -ne 2000000 || $warmup_iterations -ne 100000 \
    || $batch_size -ne 256 || $blocks -ne 12 || $aa_blocks -ne 4 \
    || $seed -ne 20260826 ]]; then
    printf 'invocation violates the fixed Topic 47 publication contract in rounds/01.md\n' >&2
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
        [[ $runtime_hostname == "$SSH_TARGET_LABEL" ]] || {
            printf 'runtime host is not the authorized Arm target\n' >&2
            exit 2
        }
        ;;
    *)
        printf 'unauthorized Topic 47 target: %s\n' "$SSH_TARGET_LABEL" >&2
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

python3 -I -B - "$coordinator_cpu" "$worker_cpu_csv" <<'PY'
import os
import pathlib
import sys

coordinator = int(sys.argv[1])
workers = [int(value) for value in sys.argv[2].split(",")]
cpus = workers + [coordinator]
if len(cpus) != len(set(cpus)):
    raise SystemExit("coordinator and worker CPUs must be distinct")
allowed = os.sched_getaffinity(0)
if any(cpu not in allowed for cpu in cpus):
    raise SystemExit(f"requested CPUs {cpus} are not contained in allowed set {sorted(allowed)}")

def topology(cpu, name):
    return pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}/topology/{name}").read_text().strip()

def node(cpu):
    nodes = list(pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}").glob("node[0-9]*"))
    if len(nodes) != 1:
        raise SystemExit(f"cpu{cpu} does not expose exactly one NUMA node")
    return int(nodes[0].name.removeprefix("node"))

locations = [(topology(cpu, "physical_package_id"), topology(cpu, "core_id")) for cpu in cpus]
if len(set(locations)) != len(locations):
    raise SystemExit("publication CPUs must occupy distinct physical cores")
if len({location[0] for location in locations}) != 1:
    raise SystemExit("publication CPUs must remain in one socket")
if len({node(cpu) for cpu in cpus}) != 1:
    raise SystemExit("publication CPUs must remain in one NUMA node")
for cpu in cpus:
    line_files = list(pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}/cache").glob("index*/coherency_line_size"))
    sizes = {int(path.read_text()) for path in line_files}
    if not sizes or any(size <= 0 or 128 % size for size in sizes):
        raise SystemExit(f"cpu{cpu} coherence-line sizes do not divide 128: {sorted(sizes)}")
PY

mkdir -p -- "$output_dir"
install -m 0400 -- "$source_archive_input" "$output_dir/source-archive.tar.gz"
source_archive="$output_dir/source-archive.tar.gz"
actual_archive_sha256=$(sha256sum -- "$source_archive" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$SOURCE_ARCHIVE_SHA256" ]]; then
    printf 'copied source archive digest mismatch\n' >&2
    exit 2
fi
python3 -I -B - "$source_archive" "$SOURCE_COMMIT" <<'PY'
import pathlib
import sys
import tarfile

with tarfile.open(sys.argv[1], "r:gz") as archive:
    declared = archive.pax_headers.get("comment")
    members = archive.getmembers()
    if declared is None:
        declared = next(
            (member.pax_headers.get("comment") for member in members if member.pax_headers.get("comment")),
            None,
        )
    if declared != sys.argv[2]:
        raise SystemExit(f"source archive does not embed commit {sys.argv[2]}")
    names = set()
    normalized_names = set()
    roots = set()
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        normalized = str(path)
        if (
            member.name in names
            or normalized in normalized_names
            or path.is_absolute()
            or ".." in path.parts
        ):
            raise SystemExit(f"unsafe or duplicate archive member: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise SystemExit(f"unsupported archive member: {member.name}")
        names.add(member.name)
        normalized_names.add(normalized)
        if path.parts:
            roots.add(path.parts[0])
    if len(roots) != 1:
        raise SystemExit("source archive must have one top-level root")
PY
source_tree=$(mktemp -d)
private=$(mktemp -d)
validation_tmp="$output_dir/.receipt-validation.json.tmp"
trap 'rm -rf -- "$source_tree" "$private"; rm -f -- "$validation_tmp"' EXIT
tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_tree"
runner_relative=topics/047-atomics-under-contention/experiment/run_host.sh
mapfile -t archived_runners < <(
    rg --files --hidden --no-ignore "$source_tree" | rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 47 host runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/047-atomics-under-contention/experiment"
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
    printf 'receipt_output_dir=%s\n' "$output_dir"
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel_release=%s\n' "$(uname -r)"
    printf 'threads=%s\n' "$threads"
    printf 'coordinator_cpu=%s\n' "$coordinator_cpu"
    printf 'worker_cpus=%s\n' "$worker_cpu_csv"
    printf 'iterations_per_thread=%s\n' "$iterations"
    printf 'warmup_iterations_per_thread=%s\n' "$warmup_iterations"
    printf 'batch_size=%s\n' "$batch_size"
    printf 'blocks=%s\n' "$blocks"
    printf 'aa_blocks=%s\n' "$aa_blocks"
    printf 'seed=%s\n' "$seed"
    printf 'process_timeout_seconds=120\n'
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'allowed_affinity=%s\n' "$(taskset --pid --cpu-list $$)"
    printf 'build_flags=RUSTFLAGS=-C target-cpu=native CARGO_INCREMENTAL=0 CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1 CARGO_PROFILE_RELEASE_LTO=fat CARGO_PROFILE_RELEASE_DEBUG=2 cargo build --locked --offline --release --package atomics-under-contention --example atomic_contention\n'
    python3 -I -B - "$coordinator_cpu" "$worker_cpu_csv" <<'PY'
import pathlib
import sys

cpus = [int(value) for value in sys.argv[2].split(",")] + [int(sys.argv[1])]
for cpu in cpus:
    root = pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}")
    node = next(root.glob("node[0-9]*")).name.removeprefix("node")
    core = (root / "topology/core_id").read_text().strip()
    package = (root / "topology/physical_package_id").read_text().strip()
    siblings = (root / "topology/thread_siblings_list").read_text().strip()
    sizes = sorted({int(path.read_text()) for path in (root / "cache").glob("index*/coherency_line_size")})
    print(f"cpu_{cpu}_core_id={core}")
    print(f"cpu_{cpu}_package_id={package}")
    print(f"cpu_{cpu}_node={node}")
    print(f"cpu_{cpu}_thread_siblings={siblings}")
    print(f"cpu_{cpu}_coherence_line_sizes={','.join(map(str, sizes))}")
PY
    printf '[uname]\n'; uname -a
    printf '[lscpu]\n'; lscpu
    printf '[lscpu-topology]\n'; lscpu -e=CPU,NODE,SOCKET,CORE,CACHE,ONLINE
    printf '[rustc]\n'; rustc -Vv
    printf '[cargo]\n'; cargo -Vv
    printf '[gcc]\n'; gcc --version
    printf '[python]\n'; python3 --version
    printf '[objdump]\n'; objdump --version
    printf '[nm]\n'; nm --version
    printf '[timeout]\n'; timeout --version
    printf '[rustc-native-cfg]\n'; rustc -C target-cpu=native --print cfg
    printf '[rustc-target-features]\n'; rustc --print target-features
    printf '[end-host]\n'
} >"$output_dir/host.txt" 2>&1

(
    cd -- "$archive_repo_root"
    export CARGO_TARGET_DIR="$private/gate-target"
    cargo fmt --all -- --check
    cargo test --locked --offline --package atomics-under-contention --lib --examples
    cargo test --locked --offline --package atomics-under-contention --doc
    cargo clippy --locked --offline --package atomics-under-contention --all-targets -- -D warnings
    cargo bench --locked --offline --package atomics-under-contention --no-run
    RUSTDOCFLAGS='-D warnings' cargo doc --locked --offline --package atomics-under-contention --no-deps
    printf 'CORRECTNESS_STATUS=pass\n'
) >"$output_dir/correctness.txt" 2>&1

(
    cd -- "$archive_repo_root"
    printf 'COMMAND=RUSTFLAGS=-C target-cpu=native CARGO_INCREMENTAL=0 CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1 CARGO_PROFILE_RELEASE_LTO=fat CARGO_PROFILE_RELEASE_DEBUG=2 cargo build --locked --offline --release --package atomics-under-contention --example atomic_contention\n'
    CARGO_TARGET_DIR="$private/release-target" \
        CARGO_INCREMENTAL=0 \
        CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1 \
        CARGO_PROFILE_RELEASE_LTO=fat \
        CARGO_PROFILE_RELEASE_DEBUG=2 \
        RUSTFLAGS='-C target-cpu=native' \
        cargo build --locked --offline --release \
            --package atomics-under-contention --example atomic_contention
    printf 'BUILD_STATUS=pass\n'
) >"$output_dir/build.txt" 2>&1

mkdir -- "$output_dir/binary"
install -m 0500 -- "$private/release-target/release/examples/atomic_contention" \
    "$output_dir/binary/atomic_contention"
binary="$output_dir/binary/atomic_contention"
sha256sum -- "$binary" >"$output_dir/binary.sha256"

mkdir -- "$output_dir/smoke"
for mode in shared cas striped batched; do
    if timeout --signal=TERM --kill-after=5s 30s \
        env BENCH_LABEL="smoke:${mode}" "$binary" "$mode" 8 10000 1000 256 8 \
        0,1,2,3,4,5,6,7 >"$output_dir/smoke/${mode}.json" \
        2>"$output_dir/smoke/${mode}.stderr"; then
        smoke_returncode=0
    else
        smoke_returncode=$?
    fi
    smoke_timed_out=false
    if [[ $smoke_returncode -eq 124 || $smoke_returncode -eq 137 ]]; then
        smoke_timed_out=true
    fi
    {
        printf 'returncode=%s\n' "$smoke_returncode"
        printf 'timed_out=%s\n' "$smoke_timed_out"
        printf 'timeout_seconds=30\n'
    } >"$output_dir/smoke/${mode}.status"
    if [[ $smoke_returncode -ne 0 ]]; then
        printf '%s smoke probe failed with status %s\n' "$mode" "$smoke_returncode" >&2
        exit 2
    fi
done

mkdir -- "$output_dir/codegen"
objdump -d -C --no-show-raw-insn "$binary" >"$output_dir/codegen/all.asm"
nm -n -C --defined-only "$binary" >"$output_dir/codegen/symbols.txt"
python3 -I -B - "$output_dir/codegen/all.asm" "$output_dir/codegen" <<'PY'
import pathlib
import re
import sys

source = pathlib.Path(sys.argv[1]).read_text()
destination = pathlib.Path(sys.argv[2])
symbols = (
    "topic47_shared_fetch_add",
    "topic47_cas_increment",
    "topic47_striped_fetch_add",
    "topic47_batched_fetch_add",
)
lines = source.splitlines()
for symbol in symbols:
    start = next((index for index, line in enumerate(lines) if line.strip().endswith(f"<{symbol}>:")), None)
    if start is None:
        raise SystemExit(f"linked image lacks {symbol}")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if re.match(r"^[0-9a-f]+ <.*>:$", lines[index].strip()):
            end = index
            break
    body = "\n".join(lines[start:end]) + "\n"
    if len(body.splitlines()) < 2:
        raise SystemExit(f"linked image has no body for {symbol}")
    (destination / f"{symbol}.asm").write_text(body)
PY

aarch64_has_add_lowering() {
    local assembly_path=$1
    if rg -q '\b((ldadd|stadd)[a-z]*|__aarch64_ldadd)' "$assembly_path"; then
        return 0
    fi
    rg -q '\b(ldxr|ldaxr)\b' "$assembly_path" && \
        rg -q '\b(stxr|stlxr)\b' "$assembly_path"
}

aarch64_has_cas_lowering() {
    local assembly_path=$1
    if rg -q '\b(cas(a|l|al)?\b|__aarch64_cas)' "$assembly_path"; then
        return 0
    fi
    rg -q '\b(ldxr|ldaxr)\b' "$assembly_path" && \
        rg -q '\b(stxr|stlxr)\b' "$assembly_path"
}

case $architecture in
    x86_64)
        rg -q '\block\b.*\b(inc|add|xadd)' "$output_dir/codegen/topic47_shared_fetch_add.asm"
        rg -q '\block\b.*\bcmpxchg' "$output_dir/codegen/topic47_cas_increment.asm"
        rg -q '\block\b.*\b(inc|add|xadd)' "$output_dir/codegen/topic47_striped_fetch_add.asm"
        rg -q '\block\b.*\b(inc|add|xadd)' "$output_dir/codegen/topic47_batched_fetch_add.asm"
        ;;
    aarch64 | arm64)
        aarch64_has_add_lowering "$output_dir/codegen/topic47_shared_fetch_add.asm"
        aarch64_has_cas_lowering "$output_dir/codegen/topic47_cas_increment.asm"
        aarch64_has_add_lowering "$output_dir/codegen/topic47_striped_fetch_add.asm"
        aarch64_has_add_lowering "$output_dir/codegen/topic47_batched_fetch_add.asm"
        ;;
esac
printf '{"status":"PASS","architecture":"%s","symbols_checked":4}\n' "$architecture" \
    >"$output_dir/codegen/codegen-check.json"
(
    cd -- "$output_dir"
    sha256sum -- codegen/all.asm codegen/symbols.txt \
        codegen/topic47_shared_fetch_add.asm codegen/topic47_cas_increment.asm \
        codegen/topic47_striped_fetch_add.asm codegen/topic47_batched_fetch_add.asm \
        >codegen/sha256sums.txt
)

python3 -I -B "$archive_script_dir/run_processes.py" \
    --binary "$binary" --out "$output_dir/experiment" \
    --threads "$threads" --iterations "$iterations" \
    --warmup-iterations "$warmup_iterations" --batch-size "$batch_size" \
    --coordinator-cpu "$coordinator_cpu" --worker-cpus "$worker_cpu_csv" \
    --blocks "$blocks" --aa-blocks "$aa_blocks" --seed "$seed" \
    --timeout-seconds 120 >"$output_dir/run-processes.txt" 2>&1

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff"

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-label "$SSH_TARGET_LABEL" \
    --expected-resolved-host "$SSH_RESOLVED_HOSTNAME" \
    --expected-source-commit "$SOURCE_COMMIT" \
    --expected-archive-sha256 "$SOURCE_ARCHIVE_SHA256" \
    --expected-architecture "$architecture" --output "$validation_tmp"

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
