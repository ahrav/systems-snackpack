#!/usr/bin/env bash
set -euo pipefail

export LANG=C
export LC_ALL=C
export TZ=UTC
export PYTHONDONTWRITEBYTECODE=1
unset BASH_ENV CDPATH ENV GLOBIGNORE LD_PRELOAD PYTHONHOME PYTHONPATH

usage() {
    printf 'usage: %s OUTPUT_DIR TARGET_LABEL EXPECTED_HOSTNAME EXPECTED_ARCHITECTURE\n' "$0" >&2
}

if [[ $# -eq 1 && $1 == --help ]]; then
    usage
    exit 0
fi
if [[ $# -ne 4 ]]; then
    usage
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 51 host receipts require Linux\n' >&2
    exit 2
fi

: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the source archive SHA-256}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"

output_dir=$(realpath -m -- "$1")
target_label=$2
expected_hostname=$3
expected_architecture=$4
source_commit=${SOURCE_COMMIT,,}
source_archive_sha256=${SOURCE_ARCHIVE_SHA256,,}
source_archive_input=$(realpath -- "$SOURCE_ARCHIVE_PATH")
data_parent=${TOPIC51_DATA_PARENT:-/var/tmp}
arm_target=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
build_flags=(-O3 -g -std=c11 -Wall -Wextra -Werror -march=native)

rustc_path=$(command -v rustc) || {
    printf 'Topic 51 publication receipts require rustc in the host environment\n' >&2
    exit 2
}
if [[ $rustc_path != /* || ! -x $rustc_path ]]; then
    printf 'rustc must resolve to an executable absolute path, got %s\n' "$rustc_path" >&2
    exit 2
fi
rustc_version=$("$rustc_path" -Vv) || {
    printf 'failed to record the Rust toolchain through %s\n' "$rustc_path" >&2
    exit 2
}

sysctl_path=$(command -v sysctl) || {
    printf 'Topic 51 publication receipts require sysctl in the host environment\n' >&2
    exit 2
}
if [[ $sysctl_path != /* || ! -x $sysctl_path ]]; then
    printf 'sysctl must resolve to an executable absolute path, got %s\n' "$sysctl_path" >&2
    exit 2
fi

if [[ ! $source_commit =~ ^[0-9a-f]{40}$ || ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'source commit or archive digest has the wrong shape\n' >&2
    exit 2
fi
if [[ ! -f $source_archive_input ]]; then
    printf 'SOURCE_ARCHIVE_PATH is not a regular file\n' >&2
    exit 2
fi
if [[ -e $output_dir ]]; then
    printf 'output path already exists: %s\n' "$output_dir" >&2
    exit 2
fi

runtime_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $runtime_hostname != "$expected_hostname" ]]; then
    printf 'runtime hostname %s differs from controller expectation %s\n' \
        "$runtime_hostname" "$expected_hostname" >&2
    exit 2
fi
case $target_label in
    xxl)
        if [[ $expected_architecture != x86_64 || $architecture != x86_64 ]]; then
            printf 'runtime-resolved xxl must be x86_64\n' >&2
            exit 2
        fi
        ;;
    "$arm_target")
        if [[ $expected_hostname != "$arm_target" || \
              $expected_architecture != aarch64 || $architecture != aarch64 ]]; then
            printf 'literal Arm target identity or architecture changed\n' >&2
            exit 2
        fi
        ;;
    *)
        printf 'unauthorized Topic 51 target label: %s\n' "$target_label" >&2
        exit 2
        ;;
esac

actual_archive_sha256=$(sha256sum -- "$source_archive_input" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$source_archive_sha256" ]]; then
    printf 'uploaded source archive digest mismatch\n' >&2
    exit 2
fi

private_dir=$(mktemp -d /tmp/topic51-private.XXXXXX)
source_tree=$(mktemp -d /tmp/topic51-source.XXXXXX)
data_dir=""
cleanup() {
    local prior_status=$?
    if [[ -n $data_dir && -d $data_dir ]]; then
        rm -f -- "$data_dir/data.bin" "$data_dir/writecheck.bin"
        rmdir -- "$data_dir" 2>/dev/null || true
    fi
    python3 -I -B - "$private_dir" "$source_tree" <<'PY' || true
import pathlib
import shutil
import sys

for raw in sys.argv[1:]:
    path = pathlib.Path(raw)
    if path.exists():
        shutil.rmtree(path)
PY
    return "$prior_status"
}
trap cleanup EXIT

python3 -I -B - "$source_archive_input" "$source_commit" <<'PY'
import pathlib
import sys
import tarfile

archive_path = pathlib.Path(sys.argv[1])
commit = sys.argv[2]
prefix = f"systems-snackpack-{commit}/"
topic = prefix + "topics/051-page-cache-io/"
required = {
    topic + "experiment/README.md",
    topic + "experiment/pcbench.c",
    topic + "experiment/run_processes.py",
    topic + "experiment/analyze.py",
    topic + "experiment/validate_receipts.py",
    topic + "experiment/run_host.sh",
}
with tarfile.open(archive_path, "r:gz") as archive:
    members = archive.getmembers()
    embedded = archive.pax_headers.get("comment")
    if embedded is None:
        embedded = next(
            (member.pax_headers.get("comment") for member in members if member.pax_headers.get("comment")),
            None,
        )
    if embedded != commit:
        raise SystemExit("source archive does not embed the expected commit")
    if len(members) > 512:
        raise SystemExit("source archive exceeds 512 members")
    seen = set()
    files = set()
    total = 0
    for member in members:
        path = pathlib.PurePosixPath(member.name)
        if (
            member.name in seen
            or path.is_absolute()
            or ".." in path.parts
            or not (member.isdir() or member.isfile())
        ):
            raise SystemExit(f"unsafe or duplicate archive member: {member.name}")
        if member.name != prefix.rstrip("/") and not member.name.startswith(prefix):
            raise SystemExit(f"archive member escaped unique prefix: {member.name}")
        if member.isfile() and not member.name.startswith(topic):
            raise SystemExit(f"archive file escaped Topic 51: {member.name}")
        seen.add(member.name)
        if member.isfile():
            files.add(member.name)
            total += member.size
    if not required.issubset(files):
        raise SystemExit(f"archive lacks required experiment files: {sorted(required - files)}")
    if len(files) > 256 or total > 32 * 1024 * 1024:
        raise SystemExit("source archive exceeds file-count or uncompressed-byte cap")
PY

tar -xzf "$source_archive_input" -C "$source_tree"
runner_relative=topics/051-page-cache-io/experiment/run_host.sh
mapfile -t archived_runners < <(
    rg --files --hidden --no-ignore "$source_tree" | rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 51 runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/051-page-cache-io/experiment"
if ! cmp -s -- "${BASH_SOURCE[0]}" "$archive_script_dir/run_host.sh"; then
    printf 'executing host runner differs from archived runner\n' >&2
    exit 2
fi
case $output_dir/ in
    "$archive_repo_root"/*)
        printf 'write receipts outside the extracted source tree\n' >&2
        exit 2
        ;;
esac

write_source_manifest() {
    local destination=$1
    (
        cd "$archive_repo_root"
        mapfile -t paths < <(rg --files topics/051-page-cache-io | LC_ALL=C sort)
        if ((${#paths[@]} == 0)); then
            printf 'source manifest found no Topic 51 files\n' >&2
            exit 2
        fi
        sha256sum -- "${paths[@]}"
    ) >"$destination"
}

compiler_macros=$(env -i PATH=/bin:/usr/bin LC_ALL=C \
    cc -E -dM -x c /dev/null 2>/dev/null) || compiler_macros=""
if ! rg -q '__GNUC__' <<<"$compiler_macros" || rg -q '__clang__' <<<"$compiler_macros"; then
    printf 'Topic 51 publication receipts require GCC\n' >&2
    exit 2
fi

if [[ ! -d $data_parent || ! -w $data_parent ]]; then
    printf 'data parent is not a writable directory: %s\n' "$data_parent" >&2
    exit 2
fi
data_fstype=$(findmnt -n -T "$data_parent" -o FSTYPE)
case $data_fstype in
    tmpfs|ramfs)
        printf 'data parent must use a block-backed filesystem, got %s\n' "$data_fstype" >&2
        exit 2
        ;;
esac
data_dir=$(mktemp -d "$data_parent/topic51-data.XXXXXX")
chmod 0700 "$data_dir"

mkdir -p -- "$output_dir" "$output_dir/build" "$output_dir/bin" \
    "$output_dir/codegen" "$output_dir/controls" "$output_dir/campaign"
install -m 0400 -- "$source_archive_input" "$output_dir/source-archive.tar.gz"
write_source_manifest "$output_dir/source-manifest-before.sha256"
install -m 0400 -- "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-files.sha256"

python3 -I -B - "$output_dir/host.json" "$target_label" "$expected_hostname" \
    "$expected_architecture" "$source_commit" "$source_archive_sha256" \
    "$data_parent" "$data_dir" "$rustc_path" "$rustc_version" \
    "$sysctl_path" <<'PY'
import glob
import json
import os
import pathlib
import platform
import subprocess
import sys

(
    output,
    label,
    expected_host,
    expected_arch,
    commit,
    archive_sha,
    data_parent,
    data_dir,
    rustc_path,
    rustc_version,
    sysctl_path,
) = sys.argv[1:]

def command(argv):
    try:
        process = subprocess.run(
            argv,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            env={"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"},
        )
    except FileNotFoundError as error:
        return {"argv": argv, "returncode": 127, "output": str(error)}
    return {"argv": argv, "returncode": process.returncode, "output": process.stdout.strip()}

def selected(path, names):
    result = {}
    with open(path, encoding="utf-8") as source:
        for line in source:
            pieces = line.split()
            if len(pieces) >= 2 and pieces[0].rstrip(":") in names:
                result[pieces[0].rstrip(":")] = pieces[1]
    return result

queue = {}
for raw in sorted(glob.glob("/sys/block/*/queue")):
    base = pathlib.Path(raw)
    fields = {}
    for name in (
        "read_ahead_kb",
        "logical_block_size",
        "physical_block_size",
        "max_sectors_kb",
        "nr_requests",
        "rotational",
        "scheduler",
    ):
        path = base / name
        try:
            fields[name] = path.read_text(encoding="utf-8").strip()
        except OSError as error:
            fields[name] = {"error": str(error)}
    queue[base.parent.name] = fields

value = {
    "schema": "topic51-host.v1",
    "target_label": label,
    "expected_hostname": expected_host,
    "expected_architecture": expected_arch,
    "runtime_hostname": command(["hostname", "-f"]),
    "uname": command(["uname", "-a"]),
    "machine": platform.machine(),
    "kernel_release": platform.release(),
    "source_commit": commit,
    "source_archive_sha256": archive_sha,
    "page_size": os.sysconf("SC_PAGE_SIZE"),
    "configured_cpu_count": os.cpu_count(),
    "allowed_affinity": sorted(os.sched_getaffinity(0)),
    "data_parent": data_parent,
    "data_dir": data_dir,
    "lscpu": command(["lscpu", "-J"]),
    "findmnt_tmp": command(["findmnt", "-J", "-T", "/tmp"]),
    "findmnt_data": command(["findmnt", "-J", "-T", data_dir]),
    "df_data": command(["df", "-PT", data_dir]),
    "lsblk": command([
        "lsblk", "-J", "-o",
        "NAME,KNAME,TYPE,MAJ:MIN,PKNAME,SIZE,ROTA,SCHED,MODEL,SERIAL",
    ]),
    "free": command(["free", "-b"]),
    "compiler": command(["cc", "--version"]),
    "compiler_target": command(["cc", "-march=native", "-Q", "--help=target"]),
    "python": command(["python3", "--version"]),
    "rust": {
        "argv": [rustc_path, "-Vv"],
        "returncode": 0,
        "output": rustc_version,
    },
    "sysctl": command([
        sysctl_path,
        "vm.dirty_ratio",
        "vm.dirty_background_ratio",
        "vm.dirty_bytes",
        "vm.dirty_background_bytes",
        "vm.dirty_expire_centisecs",
        "vm.dirty_writeback_centisecs",
        "vm.swappiness",
    ]),
    "meminfo": selected(
        "/proc/meminfo",
        {"MemTotal", "MemAvailable", "Cached", "Buffers", "Dirty", "Writeback"},
    ),
    "vmstat": selected(
        "/proc/vmstat",
        {
            "nr_dirty",
            "nr_writeback",
            "nr_dirty_threshold",
            "nr_dirty_background_threshold",
            "pgpgin",
            "pgpgout",
            "workingset_refault_file",
        },
    ),
    "pressure_io": pathlib.Path("/proc/pressure/io").read_text(encoding="utf-8").strip(),
    "diskstats": pathlib.Path("/proc/diskstats").read_text(encoding="utf-8").strip(),
    "block_queue": queue,
    "iostat": command(["iostat", "-xz", "1", "1"]),
}
pathlib.Path(output).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

{
    printf '[compiler]\n'
    cc --version
    printf '[build-command]\n'
    printf 'cc'
    printf ' %q' "${build_flags[@]}" "$archive_script_dir/pcbench.c"
    printf ' -o %q\n' "$output_dir/bin/pcbench"
} >"$output_dir/build/identity.txt"

set +e
env -i PATH=/bin:/usr/bin LANG=C LC_ALL=C TZ=UTC \
    cc "${build_flags[@]}" "$archive_script_dir/pcbench.c" \
    -o "$output_dir/bin/pcbench" \
    >"$output_dir/build/compile.stdout" 2>"$output_dir/build/compile.stderr"
compile_status=$?
set -e
python3 -I -B - "$output_dir/build/compile.status.json" "$compile_status" <<'PY'
import json
import pathlib
import sys
pathlib.Path(sys.argv[1]).write_text(
    json.dumps({"returncode": int(sys.argv[2])}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
PY
if ((compile_status != 0)); then
    printf 'native build failed\n' >&2
    exit 1
fi

env -i PATH=/bin:/usr/bin LANG=C LC_ALL=C TZ=UTC \
    cc "${build_flags[@]}" -S -fverbose-asm "$archive_script_dir/pcbench.c" \
    -o "$output_dir/codegen/pcbench.s"
binary="$output_dir/bin/pcbench"
sha256sum -- "$binary" >"$output_dir/bin/pcbench.sha256"
file -- "$binary" >"$output_dir/bin/pcbench.file.txt"
ldd -- "$binary" >"$output_dir/bin/pcbench.ldd.txt"
readelf -nW -- "$binary" >"$output_dir/bin/pcbench.build-id.txt"
objdump -drwC --no-show-raw-insn -- "$binary" >"$output_dir/codegen/all.asm"
objdump -drwC --no-show-raw-insn --disassemble=verify_block -- "$binary" \
    >"$output_dir/codegen/verify_block.asm"
nm -an -- "$binary" >"$output_dir/codegen/symbols.txt"

run_control() {
    local name=$1
    shift
    local stdout_path="$output_dir/controls/${name}.stdout"
    local stderr_path="$output_dir/controls/${name}.stderr"
    local status_path="$output_dir/controls/${name}.status.json"
    local started ended returncode
    started=$(date +%s%N)
    set +e
    env -i PATH=/bin:/usr/bin LANG=C LC_ALL=C TZ=UTC \
        "$binary" "$@" >"$stdout_path" 2>"$stderr_path"
    returncode=$?
    set -e
    ended=$(date +%s%N)
    python3 -I -B - "$status_path" "$name" "$started" "$ended" "$returncode" \
        "$stdout_path" "$stderr_path" <<'PY'
import hashlib
import json
import pathlib
import sys

output, name, started, ended, returncode, stdout_raw, stderr_raw = sys.argv[1:]
def sha256(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
value = {
    "schema": "topic51-control-status.v1",
    "name": name,
    "started_realtime_ns": int(started),
    "ended_realtime_ns": int(ended),
    "returncode": int(returncode),
    "stdout_sha256": sha256(stdout_raw),
    "stderr_sha256": sha256(stderr_raw),
}
pathlib.Path(output).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    if ((returncode != 0)); then
        printf 'control %s failed\n' "$name" >&2
        exit 1
    fi
}

run_control prepare prepare "$data_dir/data.bin" 16
run_control probe-sequential probe "$data_dir/data.bin" probe_seq sequential_one_read
run_control probe-random probe "$data_dir/data.bin" probe_random random_one_read
run_control writecheck writecheck "$data_dir/writecheck.bin" 4

for scenario in primary aa direct; do
    python3 -I -B "$archive_script_dir/run_processes.py" \
        --binary "$binary" \
        --data-file "$data_dir/data.bin" \
        --output-dir "$output_dir/campaign/$scenario" \
        --scenario "$scenario" \
        --source-commit "$source_commit" \
        --source-archive-sha256 "$source_archive_sha256" \
        --target-label "$target_label" \
        >"$output_dir/campaign/${scenario}.controller.stdout" \
        2>"$output_dir/campaign/${scenario}.controller.stderr"
done
python3 -I -B "$archive_script_dir/analyze.py" "$output_dir/campaign" \
    >"$output_dir/campaign/summary.json"

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff" || true
if [[ -s $output_dir/source-manifest.diff ]]; then
    printf 'archived Topic 51 source changed during execution\n' >&2
    exit 1
fi

rm -- "$data_dir/data.bin" "$data_dir/writecheck.bin"
rmdir -- "$data_dir"
data_dir=""
python3 -I -B - "$output_dir/cleanup.json" "$data_parent" <<'PY'
import json
import pathlib
import sys
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "schema": "topic51-cleanup.v1",
            "data_parent": sys.argv[2],
            "removed_files": ["data.bin", "writecheck.bin"],
            "data_directory_removed": True,
        },
        indent=2,
        sort_keys=True,
    ) + "\n",
    encoding="utf-8",
)
PY

preseal_validation="$private_dir/preseal-validation.json"
python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-target-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-source-commit "$source_commit" \
    --expected-source-archive-sha256 "$source_archive_sha256" \
    >"$preseal_validation"
install -m 0400 -- "$preseal_validation" "$output_dir/receipt-validation.json"

(
    cd "$output_dir"
    mapfile -t receipt_files < <(
        rg --files --hidden --no-ignore | rg -v '^(MANIFEST\.sha256|SEALED)$' | LC_ALL=C sort
    )
    sha256sum -- "${receipt_files[@]}" >MANIFEST.sha256
)
printf 'topic51-receipt.v1\n' >"$output_dir/SEALED"
chmod -R a-w -- "$output_dir"

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-target-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-source-commit "$source_commit" \
    --expected-source-archive-sha256 "$source_archive_sha256" \
    >/dev/null

printf 'sealed Topic 51 receipt: %s\n' "$output_dir"
