#!/usr/bin/env bash
set -euo pipefail

export LANG=C
export LC_ALL=C
export TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
unset BASH_ENV CDPATH ENV GLOBIGNORE LD_PRELOAD PYTHONHOME PYTHONPATH

usage() {
    printf 'usage: %s OUTPUT_DIR TARGET_LABEL EXPECTED_HOSTNAME EXPECTED_ARCH [PROBE_CPU WORKER_CPU_CSV]\n' "$0" >&2
}

if [[ $# -eq 1 && $1 == --help ]]; then
    usage
    exit 0
fi
if [[ $# -ne 4 && $# -ne 6 ]]; then
    usage
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 49 host receipts require Linux\n' >&2
    exit 2
fi
: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the source archive SHA-256}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"

output_dir=$(realpath -m -- "$1")
target_label=$2
expected_hostname=$3
expected_architecture=$4
if [[ $# -eq 6 ]]; then
    probe_cpu=$5
    worker_cpu_csv=$6
    cpu_selection=explicit
else
    probe_cpu=0
    worker_cpu_csv=1,2,3,4,5,6,7,8
    cpu_selection=verified-default
fi
source_commit=${SOURCE_COMMIT,,}
source_archive_sha256=${SOURCE_ARCHIVE_SHA256,,}

if [[ ! $source_commit =~ ^[0-9a-f]{40}$ || ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'source commit or archive digest has the wrong shape\n' >&2
    exit 2
fi
if [[ ! -f $SOURCE_ARCHIVE_PATH ]]; then
    printf 'SOURCE_ARCHIVE_PATH is not a regular file\n' >&2
    exit 2
fi
source_archive_input=$(realpath -- "$SOURCE_ARCHIVE_PATH")
if [[ ! $probe_cpu =~ ^[0-9]+$ || ! $worker_cpu_csv =~ ^[0-9]+(,[0-9]+){7}$ ]]; then
    printf 'probe CPU must be nonnegative and worker list must contain eight integers\n' >&2
    exit 2
fi
if [[ -e $output_dir ]]; then
    printf 'output path already exists: %s\n' "$output_dir" >&2
    exit 2
fi

runtime_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $runtime_hostname != "$expected_hostname" ]]; then
    printf 'runtime hostname %s differs from expected %s\n' "$runtime_hostname" "$expected_hostname" >&2
    exit 2
fi
if [[ $architecture != "$expected_architecture" ]]; then
    printf 'runtime architecture %s differs from expected %s\n' "$architecture" "$expected_architecture" >&2
    exit 2
fi
arm_target=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
case $target_label in
    xxl)
        [[ $expected_architecture == x86_64 ]] || {
            printf 'runtime-resolved xxl target must be x86_64\n' >&2
            exit 2
        }
        ;;
    "$arm_target")
        [[ $expected_hostname == "$arm_target" ]] || {
            printf 'literal Arm target hostname changed\n' >&2
            exit 2
        }
        [[ $expected_architecture == aarch64 ]] || {
            printf 'literal Arm target must report AArch64\n' >&2
            exit 2
        }
        ;;
    *)
        printf 'unauthorized Topic 49 target label: %s\n' "$target_label" >&2
        exit 2
        ;;
esac

private_dir=$(mktemp -d)
source_tree=$(mktemp -d)
topology_tmp=$(mktemp)
preseal_validation="$private_dir/preseal-validation.json"
final_validation="$private_dir/final-validation.json"
trap 'rm -rf -- "$private_dir" "$source_tree"; rm -f -- "$topology_tmp"' EXIT

python3 -I -B - "$probe_cpu" "$worker_cpu_csv" >"$topology_tmp" <<'PY'
import os
import pathlib
import sys

probe = int(sys.argv[1])
workers = [int(value) for value in sys.argv[2].split(",")]
cpus = [probe, *workers]
if len(workers) != 8 or len(cpus) != len(set(cpus)):
    raise SystemExit("probe and eight worker CPUs must be distinct")
allowed = os.sched_getaffinity(0)
if any(cpu not in allowed for cpu in cpus):
    raise SystemExit(f"selected CPUs {cpus} are outside allowed affinity {sorted(allowed)}")

def text(path: pathlib.Path) -> str:
    return path.read_text().strip()

def node_for(root: pathlib.Path) -> int:
    nodes = sorted(root.glob("node[0-9]*"))
    if len(nodes) != 1:
        raise SystemExit(f"{root.name} must expose exactly one NUMA node")
    return int(nodes[0].name.removeprefix("node"))

locations = []
nodes = []
for cpu in cpus:
    root = pathlib.Path(f"/sys/devices/system/cpu/cpu{cpu}")
    if not root.is_dir():
        raise SystemExit(f"cpu{cpu} does not exist")
    online = root / "online"
    if online.exists() and text(online) != "1":
        raise SystemExit(f"cpu{cpu} is offline")
    package = text(root / "topology/physical_package_id")
    core = text(root / "topology/core_id")
    siblings = text(root / "topology/thread_siblings_list")
    node = node_for(root)
    locations.append((package, core))
    nodes.append(node)
    print(f"cpu_{cpu}_package_id={package}")
    print(f"cpu_{cpu}_core_id={core}")
    print(f"cpu_{cpu}_numa_node={node}")
    print(f"cpu_{cpu}_thread_siblings={siblings}")
if len(set(locations)) != len(locations):
    raise SystemExit("selected logical CPUs do not occupy distinct physical cores")
if len(set(nodes)) != 1:
    raise SystemExit("selected CPUs do not occupy one NUMA node")
print(f"selected_numa_node={nodes[0]}")
print("distinct_physical_cores=true")
print("single_numa_node=true")
print("allowed_affinity=" + ",".join(map(str, sorted(allowed))))
PY

selected_numa_node=$(sed -n 's/^selected_numa_node=//p' -- "$topology_tmp")
if [[ ! $selected_numa_node =~ ^[0-9]+$ ]]; then
    printf 'topology probe did not produce one selected NUMA node\n' >&2
    exit 2
fi

actual_archive_sha256=$(sha256sum -- "$source_archive_input" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$source_archive_sha256" ]]; then
    printf 'uploaded source archive digest mismatch\n' >&2
    exit 2
fi

mkdir -p -- "$output_dir"
install -m 0400 -- "$source_archive_input" "$output_dir/source-archive.tar.gz"
python3 -I -B - "$output_dir/source-archive.tar.gz" "$source_commit" <<'PY'
import pathlib
import sys
import tarfile

archive_path = pathlib.Path(sys.argv[1])
expected_commit = sys.argv[2]
expected_prefix = f"systems-snackpack-{expected_commit}/"
topic_prefix = expected_prefix + "topics/049-dram-memory-controller-behavior/"
allowed_ancestor_dirs = {
    expected_prefix.rstrip("/"),
    expected_prefix + "topics",
    topic_prefix.rstrip("/"),
}
required = {
    topic_prefix + "experiment/dram_bench.c",
    topic_prefix + "experiment/run_processes.py",
    topic_prefix + "experiment/analyze.py",
    topic_prefix + "experiment/validate_receipts.py",
    topic_prefix + "experiment/run_host.sh",
}
max_files = 128
max_members = 256
max_uncompressed_bytes = 16 * 1024 * 1024
with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    embedded = archive.pax_headers.get("comment")
    if embedded is None:
        embedded = next(
            (member.pax_headers.get("comment") for member in members if member.pax_headers.get("comment")),
            None,
        )
    if embedded != expected_commit:
        raise SystemExit("source archive does not embed the expected commit")
    seen = set()
    normalized = set()
    files = set()
    total_size = 0
    if len(members) > max_members:
        raise SystemExit(f"archive exceeds {max_members} total members")
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if (
            member.name in seen
            or str(path) in normalized
            or path.is_absolute()
            or ".." in path.parts
            or not (member.isdir() or member.isfile())
        ):
            raise SystemExit(f"unsafe or duplicate archive member: {member.name}")
        if member.name != expected_prefix.rstrip("/") and not member.name.startswith(expected_prefix):
            raise SystemExit(f"archive member escaped unique prefix: {member.name}")
        if member.isfile() and not member.name.startswith(topic_prefix):
            raise SystemExit(f"archive is not path-limited to Topic 49: {member.name}")
        if member.isdir() and (
            member.name.rstrip("/") not in allowed_ancestor_dirs
            and not member.name.startswith(topic_prefix)
        ):
            raise SystemExit(f"archive directory escaped the Topic 49 ancestor tree: {member.name}")
        seen.add(member.name)
        normalized.add(str(path))
        if member.isfile():
            files.add(member.name)
            total_size += member.size
    if not required.issubset(files):
        raise SystemExit(f"archive lacks required experiment files: {sorted(required - files)}")
    if len(files) > max_files:
        raise SystemExit(f"archive exceeds {max_files} regular files")
    if total_size > max_uncompressed_bytes:
        raise SystemExit(f"archive exceeds {max_uncompressed_bytes} uncompressed bytes")
PY
tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_tree"
runner_relative=topics/049-dram-memory-controller-behavior/experiment/run_host.sh
mapfile -t archived_runners < <(
    rg --files --hidden --no-ignore "$source_tree" | rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 49 runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/049-dram-memory-controller-behavior/experiment"
if ! cmp -s -- "${BASH_SOURCE[0]}" "$archive_script_dir/run_host.sh"; then
    printf 'executing host runner differs from archived runner\n' >&2
    exit 2
fi
for name in dram_bench.c run_processes.py analyze.py validate_receipts.py run_host.sh; do
    [[ -f $archive_script_dir/$name ]] || {
        printf 'source archive lacks %s\n' "$name" >&2
        exit 2
    }
done
case $output_dir in
    "$archive_repo_root" | "$archive_repo_root"/*)
        printf 'write host receipts outside the extracted source tree\n' >&2
        exit 2
        ;;
esac

write_source_manifest() {
    local destination=$1
    (
        cd -- "$archive_repo_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum --
    ) >"$destination"
}
write_source_manifest "$output_dir/source-manifest-before.sha256"
(
    cd -- "$archive_repo_root"
    sha256sum -- \
        topics/049-dram-memory-controller-behavior/experiment/dram_bench.c \
        topics/049-dram-memory-controller-behavior/experiment/run_processes.py \
        topics/049-dram-memory-controller-behavior/experiment/analyze.py \
        topics/049-dram-memory-controller-behavior/experiment/validate_receipts.py \
        topics/049-dram-memory-controller-behavior/experiment/run_host.sh
) >"$output_dir/source-files.sha256"

capture_command() {
    local heading=$1
    shift
    printf '[%s]\n' "$heading"
    if command -v -- "$1" >/dev/null 2>&1; then
        "$@" 2>&1 || printf 'COMMAND_FAILED=%s\n' "$?"
    else
        printf 'unavailable=%s\n' "$1"
    fi
}

capture_file() {
    local heading=$1
    local path=$2
    printf '[%s]\n' "$heading"
    if [[ -r $path ]]; then
        sed -n '1,400p' -- "$path"
    else
        printf 'unavailable=%s\n' "$path"
    fi
}

cpu_model=$(lscpu | sed -n 's/^Model name:[[:space:]]*//p' | sed -n '1p')
if [[ -n $cpu_model ]]; then
    cpu_model_source=lscpu-model-name
else
    midr_path=/sys/devices/system/cpu/cpu0/regs/identification/midr_el1
    if [[ ! -r $midr_path ]]; then
        printf 'host lacks both lscpu model name and readable cpu0 MIDR\n' >&2
        exit 2
    fi
    cpu_model=$(sed -n '1p' -- "$midr_path")
    cpu_model_source=sysfs-midr-el1
fi
numa_balancing_path=/proc/sys/kernel/numa_balancing
if [[ ! -r $numa_balancing_path ]]; then
    printf 'host lacks readable automatic NUMA balancing state\n' >&2
    exit 2
fi
numa_balancing=$(sed -n '1p' -- "$numa_balancing_path")
if [[ ! $numa_balancing =~ ^[0-3]$ ]]; then
    printf 'automatic NUMA balancing state is not a valid bitmask: %s\n' "$numa_balancing" >&2
    exit 2
fi

{
    printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$source_archive_sha256"
    printf 'ssh_target_label=%s\n' "$target_label"
    printf 'expected_hostname=%s\n' "$expected_hostname"
    printf 'runtime_hostname=%s\n' "$runtime_hostname"
    printf 'expected_architecture=%s\n' "$expected_architecture"
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel_release=%s\n' "$(uname -r)"
    printf 'cpu_selection=%s\n' "$cpu_selection"
    printf 'probe_cpu=%s\n' "$probe_cpu"
    printf 'worker_cpus=%s\n' "$worker_cpu_csv"
    printf 'numa_node=%s\n' "$selected_numa_node"
    printf 'large_mib=512\n'
    printf 'worker_mib=128\n'
    printf 'warmup_ms=750\n'
    printf 'primary_blocks=12\n'
    printf 'aa_blocks=4\n'
    printf 'schedule_seed=20260828\n'
    printf 'quiet_interval_seconds=1\n'
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'cpu_model_source=%s\n' "$cpu_model_source"
    printf 'cpu_model=%s\n' "$cpu_model"
    printf 'numa_balancing=%s\n' "$numa_balancing"
    printf 'build_flags=-O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread\n'
    sed -n '1,200p' -- "$topology_tmp"
    capture_command uname uname -a
    capture_command lscpu lscpu
    printf '[cpu-model-raw]\n%s\n' "$cpu_model"
    capture_command lscpu-topology lscpu -e=CPU,NODE,SOCKET,CORE,CACHE,ONLINE
    capture_command lscpu-caches lscpu -C
    capture_command numactl numactl --hardware
    capture_file numa-online /sys/devices/system/node/online
    capture_file numa-balancing "$numa_balancing_path"
    capture_file cpu-online /sys/devices/system/cpu/online
    capture_file thp-enabled /sys/kernel/mm/transparent_hugepage/enabled
    capture_file thp-defrag /sys/kernel/mm/transparent_hugepage/defrag
    printf '[hugepages]\n'
    rg '^(AnonHugePages|ShmemHugePages|FileHugePages|HugePages_|Hugepagesize|Hugetlb):' /proc/meminfo || true
    capture_file process-cgroup /proc/self/cgroup
    capture_file cgroups /proc/cgroups
    capture_file cgroup-controllers /sys/fs/cgroup/cgroup.controllers
    capture_command rustc rustc -Vv
    capture_command cargo cargo -Vv
    capture_command command-v-gcc command -v gcc
    capture_command gcc-version gcc --version
    capture_command gcc-verbose gcc -v
    capture_command python-version python3 -VV
    capture_command gcc-native-target gcc -Q -O3 -march=native --help=target
    capture_command objdump objdump --version
    capture_command readelf readelf --version
    capture_command perf-version perf version
    capture_command perf-pmus perf list pmu
    printf '[sysfs-pmus]\n'
    for pmu in /sys/bus/event_source/devices/*; do
        [[ -e $pmu ]] && printf '%s\n' "${pmu##*/}"
    done
    capture_file loadavg /proc/loadavg
    capture_command uptime uptime
    printf '[selected-cache-topology]\n'
    for cpu in "$probe_cpu" ${worker_cpu_csv//,/ }; do
        for index in /sys/devices/system/cpu/cpu"$cpu"/cache/index*; do
            [[ -d $index ]] || continue
            printf 'cpu=%s index=%s level=%s type=%s size=%s shared_cpu_list=%s line_size=%s\n' \
                "$cpu" "${index##*/}" \
                "$(<"$index/level")" "$(<"$index/type")" "$(<"$index/size")" \
                "$(<"$index/shared_cpu_list")" "$(<"$index/coherency_line_size")"
        done
    done
    printf '[end-host]\n'
} >"$output_dir/host.txt" 2>&1

gcc_full_version=$(gcc -dumpfullversion -dumpversion)
if [[ $gcc_full_version != 11.5.0 ]]; then
    printf 'Topic 49 requires GCC 11.5.0, found %s\n' "$gcc_full_version" >&2
    exit 2
fi

build_binary="$private_dir/dram_bench"
{
    printf 'FLAGS=-O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread\n'
    printf 'COMMAND=%q' gcc
    printf ' %q' -O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread \
        "$archive_script_dir/dram_bench.c" -o "$build_binary"
    printf '\n'
    printf 'COMMAND_V_GCC=%s\n' "$(command -v gcc)"
    printf 'GCC_DUMPFULLVERSION=%s\n' "$gcc_full_version"
    gcc -v
    printf 'SOURCE=%s\n' "$archive_script_dir/dram_bench.c"
    printf 'OUTPUT=%s\n' "$build_binary"
    gcc -O3 -g -std=gnu11 -Wall -Wextra -Werror -march=native -pthread \
        "$archive_script_dir/dram_bench.c" -o "$build_binary"
    printf 'BUILD_STATUS=pass\n'
} >"$output_dir/build.txt" 2>&1

mkdir -p -- "$output_dir/binary/path-a" "$output_dir/binary/path-b"
install -m 0500 -- "$build_binary" "$output_dir/binary/path-a/dram_bench"
install -m 0500 -- "$build_binary" "$output_dir/binary/path-b/dram_bench"
(
    cd -- "$output_dir"
    sha256sum -- binary/path-a/dram_bench binary/path-b/dram_bench
) >"$output_dir/binary.sha256"
file -- "$output_dir/binary/path-a/dram_bench" "$output_dir/binary/path-b/dram_bench" \
    >"$output_dir/binary.file.txt" 2>&1
readelf -n -- "$output_dir/binary/path-a/dram_bench" >"$output_dir/binary.build-id.txt" 2>&1
ldd -- "$output_dir/binary/path-a/dram_bench" >"$output_dir/binary.ldd.txt" 2>&1

mkdir -- "$output_dir/smoke"
run_smoke() {
    local name=$1
    local treatment=$2
    local label=$3
    local binary_path=$4
    local returncode
    if timeout --signal=TERM --kill-after=5s 60s \
        env BENCH_LABEL="$label" "$binary_path" \
            --treatment "$treatment" --probe-cpu "$probe_cpu" \
            --worker-cpus "$worker_cpu_csv" --numa-node "$selected_numa_node" \
            --large-mib 8 --worker-mib 4 \
            --warmup-ms 50 >"$output_dir/smoke/$name.stdout" \
            2>"$output_dir/smoke/$name.stderr"; then
        returncode=0
    else
        returncode=$?
    fi
    local timed_out=false
    if [[ $returncode -eq 124 || $returncode -eq 137 ]]; then
        timed_out=true
    fi
    printf '{"returncode":%s,"timed_out":%s,"timeout_seconds":60}\n' \
        "$returncode" "$timed_out" >"$output_dir/smoke/$name.status.json"
    if [[ $returncode -ne 0 ]]; then
        printf 'smoke %s failed with status %s\n' "$name" "$returncode" >&2
        exit 2
    fi
}
run_smoke idle-path-a idle smoke:idle:path-a "$output_dir/binary/path-a/dram_bench"
run_smoke loaded-path-b loaded smoke:loaded:path-b "$output_dir/binary/path-b/dram_bench"
run_smoke loaded-path-a loaded smoke:loaded:path-a "$output_dir/binary/path-a/dram_bench"
python3 -I -B - "$archive_script_dir" "$output_dir/smoke" "$probe_cpu" \
    "$worker_cpu_csv" "$selected_numa_node" <<'PY'
import pathlib
import sys

script_dir = pathlib.Path(sys.argv[1])
sys.path.insert(0, str(script_dir))
from run_processes import ExpectedResult, strict_json_line, validate_result

root = pathlib.Path(sys.argv[2])
probe = int(sys.argv[3])
workers = tuple(int(value) for value in sys.argv[4].split(","))
numa_node = int(sys.argv[5])
for name, treatment, label in (
    ("idle-path-a", "idle", "smoke:idle:path-a"),
    ("loaded-path-b", "loaded", "smoke:loaded:path-b"),
    ("loaded-path-a", "loaded", "smoke:loaded:path-a"),
):
    value = strict_json_line((root / f"{name}.stdout").read_text())
    validate_result(
        value, ExpectedResult(label, treatment, probe, workers, numa_node, 8, 4, 50)
    )
PY

mkdir -- "$output_dir/codegen"
objdump -d --no-show-raw-insn -- "$output_dir/binary/path-a/dram_bench" \
    >"$output_dir/codegen/all.asm"
nm -n --defined-only -- "$output_dir/binary/path-a/dram_bench" \
    >"$output_dir/codegen/symbols.txt"
python3 -I -B - "$output_dir/codegen/all.asm" "$output_dir/codegen" "$architecture" <<'PY'
import pathlib
import re
import sys

source = pathlib.Path(sys.argv[1]).read_text()
destination = pathlib.Path(sys.argv[2])
architecture = sys.argv[3]
symbols = (
    "topic49_walk_dependent",
    "topic49_stream_scan",
    "topic49_page_prepare",
    "topic49_run_timed",
)
lines = source.splitlines(keepends=True)
headers = []
for index, line in enumerate(lines):
    match = re.match(r"^\s*[0-9a-f]+ <([^>]+)>:\s*$", line)
    if match:
        headers.append((index, match.group(1)))
for symbol in symbols:
    starts = [index for index, name in headers if name == symbol]
    if len(starts) != 1:
        raise SystemExit(f"linked image must contain exactly one disassembly header for {symbol}")
    start = starts[0]
    end = next((index for index, _ in headers if index > start), len(lines))
    text = "".join(lines[start:end])
    if not text.strip():
        raise SystemExit(f"empty linked disassembly for {symbol}")
    (destination / f"{symbol}.asm").write_text(text)

call_mnemonic = r"(?:callq?|bl)"
for target in symbols:
    if not re.search(rf"\b{call_mnemonic}\b[^\n]*<{re.escape(target)}>", source):
        raise SystemExit(f"linked disassembly lacks a call edge to {target}")

walker = (destination / "topic49_walk_dependent.asm").read_text()
stream = (destination / "topic49_stream_scan.asm").read_text()

def arm_has_next_dependent_load(assembly):
    lines = assembly.lower().splitlines()
    direct = re.compile(
        r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,"
        r"\s*\[[^\]]*,\s*(x[0-9]+)\s*,\s*lsl\s*#(?:0x)?6\]"
    )
    for line in lines:
        match = direct.search(line)
        if match and match.group(1) == match.group(2):
            return True
    indexed_add = re.compile(
        r"\badd\s+(x[0-9]+)\s*,\s*x[0-9]+\s*,\s*(x[0-9]+)\s*,\s*lsl\s*#(?:0x)?6\b"
    )
    address_load = re.compile(
        r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,\s*\[(x[0-9]+)(?:\s*,[^\]]+)?\]"
    )
    for index, line in enumerate(lines):
        address = indexed_add.search(line)
        if not address:
            continue
        address_register, next_index_register = address.groups()
        for later in lines[index + 1:index + 5]:
            loaded = address_load.search(later)
            if loaded and loaded.group(1) == next_index_register and loaded.group(2) == address_register:
                return True
    scale = re.compile(r"\blsl\s+(x[0-9]+)\s*,\s*(x[0-9]+)\s*,\s*#(?:0x)?6\b")
    load = re.compile(r"\b(?:ldr|ldp)\s+(x[0-9]+)(?:\s*,\s*x[0-9]+)?\s*,\s*\[([^\]]+)\]")
    for index, line in enumerate(lines):
        scaled = scale.search(line)
        if not scaled:
            continue
        scaled_register, next_register = scaled.groups()
        for later in lines[index + 1:index + 5]:
            loaded = load.search(later)
            if (
                loaded and loaded.group(1) == next_register
                and re.search(rf"\b{re.escape(scaled_register)}\b", loaded.group(2))
            ):
                return True
    return False

if architecture == "x86_64":
    if not re.search(r"\b(?:shl|sal)\b[^\n]*(?:^|[\s,])\$(?:0x6|6)(?=\s|,|$)", walker):
        raise SystemExit("x86-64 dependent walker lacks the 64-byte node index scale")
    if not re.search(r"\bmov[a-z]*\b[^\n]*\([^\n]*\)", walker):
        raise SystemExit("x86-64 dependent walker lacks a memory load")
    if not re.search(r"\b(?:mov|vmov|vpadd|padd)[a-z0-9]*\b[^\n]*\([^\n]*\)", stream):
        raise SystemExit("x86-64 stream kernel lacks a loop-carried memory load")
elif architecture == "aarch64":
    if not arm_has_next_dependent_load(walker):
        raise SystemExit("AArch64 dependent walker lacks a next-dependent LDR/LDP address chain")
    if not re.search(r"\b(?:ldr|ldp|ld1[a-z0-9]*)\b", stream):
        raise SystemExit("AArch64 stream kernel lacks a memory load")
else:
    raise SystemExit(f"unsupported code-generation architecture: {architecture}")
PY

{
    printf 'COMMAND=python3 -I -B run_processes.py --binary-a path-a --binary-b path-b --out experiment --probe-cpu %s --worker-cpus %s --numa-node %s --large-mib 512 --worker-mib 128 --warmup-ms 750 --seed 20260828 --timeout-seconds 300\n' \
        "$probe_cpu" "$worker_cpu_csv" "$selected_numa_node"
    python3 -I -B "$archive_script_dir/run_processes.py" \
        --binary-a "$output_dir/binary/path-a/dram_bench" \
        --binary-b "$output_dir/binary/path-b/dram_bench" \
        --out "$output_dir/experiment" \
        --probe-cpu "$probe_cpu" --worker-cpus "$worker_cpu_csv" \
        --numa-node "$selected_numa_node" \
        --large-mib 512 --worker-mib 128 --warmup-ms 750 \
        --seed 20260828 --timeout-seconds 300
    printf 'CAMPAIGN_STATUS=pass\n'
} >"$output_dir/campaign.txt" 2>&1

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff" || {
    printf 'extracted source tree changed during host execution\n' >&2
    exit 2
}

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-target-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-source-commit "$source_commit" \
    --expected-source-archive-sha256 "$source_archive_sha256" \
    --allow-unsealed --output "$preseal_validation"
install -m 0400 -- "$preseal_validation" "$output_dir/receipt-validation.json"

python3 -I -B - "$output_dir" >"$output_dir/MANIFEST.sha256" <<'PY'
import hashlib
import os
import pathlib
import stat
import sys

root = pathlib.Path(sys.argv[1])
excluded = {"MANIFEST.sha256", "SEALED"}
files = []
stack = [root]
while stack:
    directory = stack.pop()
    with os.scandir(directory) as entries:
        for entry in entries:
            path = pathlib.Path(entry.path)
            relative = path.relative_to(root).as_posix()
            mode = entry.stat(follow_symlinks=False).st_mode
            if relative in excluded:
                continue
            if stat.S_ISLNK(mode):
                raise SystemExit(f"receipt contains a symbolic link: {relative}")
            if stat.S_ISDIR(mode):
                stack.append(path)
            elif stat.S_ISREG(mode):
                files.append((relative, path))
            else:
                raise SystemExit(f"receipt contains a special entry: {relative}")
for relative, path in sorted(files):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    print(f"{digest.hexdigest()}  {relative}")
PY
manifest_sha256=$(sha256sum -- "$output_dir/MANIFEST.sha256" | awk '{print $1}')
manifest_file_count=$(wc -l <"$output_dir/MANIFEST.sha256")
printf '{"schema":"topic49-seal.v1","manifest_sha256":"%s","file_count":%s}\n' \
    "$manifest_sha256" "$manifest_file_count" >"$output_dir/SEALED"
chmod -R a-w -- "$output_dir"

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-target-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-source-commit "$source_commit" \
    --expected-source-archive-sha256 "$source_archive_sha256" \
    --output "$final_validation"
if ! cmp -s -- "$preseal_validation" "$final_validation"; then
    printf 'sealed validation differs from pre-seal validation\n' >&2
    exit 2
fi
sed -n '1,240p' -- "$final_validation"
