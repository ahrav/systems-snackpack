#!/usr/bin/env bash
set -euo pipefail

usage() {
    printf 'usage: run_host.sh RECEIPT TARGET_LABEL EXPECTED_HOSTNAME EXPECTED_ARCHITECTURE\n' >&2
}

if (($# != 4)); then
    usage
    exit 2
fi

receipt=$1
target_label=$2
expected_hostname=$3
expected_architecture=$4
: "${SOURCE_COMMIT:?SOURCE_COMMIT is required}"
: "${SOURCE_ARCHIVE_SHA256:?SOURCE_ARCHIVE_SHA256 is required}"
: "${SOURCE_ARCHIVE_PATH:?SOURCE_ARCHIVE_PATH is required}"

if [[ $SOURCE_COMMIT != +([0-9a-f]) || ${#SOURCE_COMMIT} -ne 40 ]]; then
    printf 'SOURCE_COMMIT must be 40 lowercase hexadecimal characters\n' >&2
    exit 2
fi
if [[ $SOURCE_ARCHIVE_SHA256 != +([0-9a-f]) || ${#SOURCE_ARCHIVE_SHA256} -ne 64 ]]; then
    printf 'SOURCE_ARCHIVE_SHA256 must be 64 lowercase hexadecimal characters\n' >&2
    exit 2
fi
if [[ $expected_architecture != aarch64 && $expected_architecture != x86_64 ]]; then
    printf 'expected architecture must be aarch64 or x86_64\n' >&2
    exit 2
fi
if [[ $receipt != /* || -e $receipt ]]; then
    printf 'receipt must be an absent absolute path\n' >&2
    exit 2
fi
if [[ $SOURCE_ARCHIVE_PATH != /* || ! -f $SOURCE_ARCHIVE_PATH ]]; then
    printf 'SOURCE_ARCHIVE_PATH must name a regular file by absolute path\n' >&2
    exit 2
fi

required_commands=(
    awk basename bash cat cc chmod cmp cp df file findmnt getconf hostname install
    ldd lsblk lscpu mkdir mktemp nm nproc objdump python3 readelf readlink rg
    rm rmdir sha256sum sort systemd-detect-virt tar uname
)
for command_name in "${required_commands[@]}"; do
    if ! command -v "$command_name" >/dev/null 2>&1; then
        printf 'required command is missing: %s\n' "$command_name" >&2
        exit 1
    fi
done
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 53 host receipts require Linux\n' >&2
    exit 1
fi

runtime_hostname=$(hostname -f)
runtime_architecture=$(uname -m)
if [[ $runtime_hostname != "$expected_hostname" ]]; then
    printf 'runtime hostname differs: expected=%s actual=%s\n' \
        "$expected_hostname" "$runtime_hostname" >&2
    exit 1
fi
if [[ $runtime_architecture != "$expected_architecture" ]]; then
    printf 'runtime architecture differs: expected=%s actual=%s\n' \
        "$expected_architecture" "$runtime_architecture" >&2
    exit 1
fi
if [[ $(getconf PAGESIZE) != 4096 ]]; then
    printf 'Topic 53 publication runs require 4096-byte pages\n' >&2
    exit 1
fi

actual_archive_sha256=$(sha256sum -- "$SOURCE_ARCHIVE_PATH" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$SOURCE_ARCHIVE_SHA256" ]]; then
    printf 'source archive SHA-256 differs\n' >&2
    exit 1
fi

data_parent=${TOPIC53_DATA_PARENT:-/var/tmp}
ops=${TOPIC53_OPS:-8192}
if [[ $data_parent != /* || ! -d $data_parent ]]; then
    printf 'TOPIC53_DATA_PARENT must name an existing absolute directory\n' >&2
    exit 2
fi
if [[ $ops != +([0-9]) || $ops -lt 256 || $ops -gt 32768 ]]; then
    printf 'TOPIC53_OPS must be between 256 and 32768\n' >&2
    exit 2
fi

source_work=$(mktemp -d /tmp/topic53-source.XXXXXXXX)
data_dir=$(mktemp -d "${data_parent%/}/topic53-data.XXXXXXXX")
data_file=$data_dir/data.bin
source_live=1
data_live=1

cleanup_work() {
    local status=$?
    if ((data_live)); then
        rm -f -- "$data_file"
        rmdir -- "$data_dir" 2>/dev/null || true
    fi
    if ((source_live)) && [[ $source_work == /tmp/topic53-source.* ]]; then
        rm -rf -- "$source_work"
    fi
    return "$status"
}
trap cleanup_work EXIT

mkdir -m 0700 -- "$receipt"
mkdir -m 0700 -- \
    "$receipt/source" "$receipt/host" "$receipt/build" "$receipt/bin" \
    "$receipt/codegen" "$receipt/controls" "$receipt/campaign"

source_prefix="systems-snackpack-${SOURCE_COMMIT}/"
topic_prefix='topics/053-nvme-blk-mq/'
external_runner=$(readlink -f -- "$0")

python3 -I -B - "$SOURCE_ARCHIVE_PATH" "$source_prefix" "$topic_prefix" <<'PY'
import pathlib
import sys
import tarfile

archive = pathlib.Path(sys.argv[1])
source_prefix = sys.argv[2]
source_root = source_prefix.rstrip("/")
topic_prefix = source_prefix + sys.argv[3]
required = {
    topic_prefix + "experiment/nvme_aio_depth_probe.c",
    topic_prefix + "experiment/run_processes.py",
    topic_prefix + "experiment/analyze.py",
    topic_prefix + "experiment/validate_receipt.py",
    topic_prefix + "experiment/test_validate_receipt.py",
    topic_prefix + "experiment/run_host.sh",
}
observed = set()
with tarfile.open(archive, "r:gz") as source:
    for member in source.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe archive path: {member.name}")
        if member.name == source_root and not member.isdir():
            raise SystemExit(f"archive root is not a directory: {member.name}")
        if member.name != source_root and not member.name.startswith(source_prefix):
            raise SystemExit(f"archive member escapes source prefix: {member.name}")
        if not (member.isdir() or member.isfile()):
            raise SystemExit(f"archive contains a non-file member: {member.name}")
        observed.add(member.name)
missing = sorted(required - observed)
if missing:
    raise SystemExit("archive lacks required files: " + ", ".join(missing))
PY

cp -- "$SOURCE_ARCHIVE_PATH" "$receipt/source/source.tar.gz"
printf '%s  source.tar.gz\n' "$SOURCE_ARCHIVE_SHA256" \
    >"$receipt/source/source-archive.sha256"
tar -xzf "$SOURCE_ARCHIVE_PATH" --no-same-owner -C "$source_work"
archive_root=$source_work/${source_prefix%/}
topic_dir=$archive_root/${topic_prefix%/}
archived_runner=$topic_dir/experiment/run_host.sh
cmp -- "$external_runner" "$archived_runner" >"$receipt/source/run-host-match.txt"

external_runner_sha256=$(sha256sum -- "$external_runner" | awk '{print $1}')
archived_runner_sha256=$(sha256sum -- "$archived_runner" | awk '{print $1}')
python3 -I -B - \
    "$receipt/provenance.json" "$target_label" "$expected_hostname" \
    "$expected_architecture" "$runtime_hostname" "$SOURCE_COMMIT" \
    "$SOURCE_ARCHIVE_SHA256" "$source_prefix" "$topic_prefix" \
    "$external_runner_sha256" "$archived_runner_sha256" <<'PY'
import json
import pathlib
import sys

keys = (
    "target_label",
    "expected_hostname",
    "expected_architecture",
    "runtime_hostname",
    "source_commit",
    "source_archive_sha256",
    "source_prefix",
    "topic_prefix",
    "external_run_host_sha256",
    "archived_run_host_sha256",
)
value = {"schema": "topic53-provenance.v1", **dict(zip(keys, sys.argv[2:]))}
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

write_source_manifest() {
    local destination=$1
    (
        cd "$archive_root"
        while IFS= read -r source_path; do
            sha256sum -- "$source_path"
        done < <(rg --files --hidden --no-ignore "$topic_prefix" | LC_ALL=C sort)
    ) >"$destination"
}
write_source_manifest "$receipt/source/source-files-before.sha256"

filesystem_source=$(findmnt -n -r -T "$data_dir" -o SOURCE)
filesystem_fstype=$(findmnt -n -r -T "$data_dir" -o FSTYPE)
filesystem_major_minor=$(findmnt -n -r -T "$data_dir" -o MAJ:MIN)
case ${filesystem_fstype,,} in
    tmpfs|ramfs|overlay|overlayfs|nfs|nfs4|cifs|9p|virtiofs|fuse.*)
        printf 'data filesystem is not an eligible block-backed local filesystem: %s\n' \
            "$filesystem_fstype" >&2
        exit 1
        ;;
esac
sysfs_device=$(readlink -f -- "/sys/dev/block/$filesystem_major_minor")
if [[ -z $sysfs_device || ! -e $sysfs_device ]]; then
    printf 'filesystem MAJ:MIN does not map to a sysfs block device\n' >&2
    exit 1
fi
filesystem_device=$(basename -- "$sysfs_device")
if [[ ! -b /dev/$filesystem_device ]]; then
    printf 'mapped filesystem device is not a block device: %s\n' \
        "$filesystem_device" >&2
    exit 1
fi
mapfile -t stack_devices < <(
    lsblk -s -n -r -o KNAME "/dev/$filesystem_device" | \
        awk 'NF && !seen[$0]++ {print $0}'
)
if ((${#stack_devices[@]} == 0)); then
    printf 'lsblk returned an empty device stack\n' >&2
    exit 1
fi
primary_device=${stack_devices[$((${#stack_devices[@]} - 1))]}
mq_found=0
for device in "${stack_devices[@]}"; do
    if [[ -d /sys/class/block/$device/mq ]]; then
        mq_found=1
    fi
done
if ((mq_found == 0)); then
    printf 'mapped block stack exposes no blk-mq hardware contexts\n' >&2
    exit 1
fi
devices_csv=$(IFS=,; printf '%s' "${stack_devices[*]}")

python3 -I -B - \
    "$receipt/host/host.json" "$target_label" "$expected_hostname" \
    "$expected_architecture" "$runtime_hostname" "$runtime_architecture" \
    "$SOURCE_COMMIT" "$SOURCE_ARCHIVE_SHA256" "$data_parent" \
    "$data_dir" "$filesystem_source" "$filesystem_fstype" \
    "$filesystem_major_minor" "$filesystem_device" "$devices_csv" \
    "$primary_device" <<'PY'
import json
import os
import pathlib
import subprocess
import sys

(
    output_path,
    target_label,
    expected_hostname,
    expected_architecture,
    runtime_hostname,
    runtime_architecture,
    source_commit,
    source_archive_sha256,
    data_parent,
    data_directory,
    filesystem_source,
    filesystem_fstype,
    filesystem_major_minor,
    filesystem_device,
    devices_csv,
    primary_device,
) = sys.argv[1:]
devices = devices_csv.split(",")


def read(path):
    try:
        return pathlib.Path(path).read_text(encoding="utf-8")
    except OSError as error:
        return f"unavailable:{error.errno}\n"


def command(argv):
    completed = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        text=True,
        capture_output=True,
        env={"LANG": "C", "LC_ALL": "C", "PATH": "/bin:/usr/bin", "TZ": "UTC"},
        check=False,
    )
    return {
        "argv": argv,
        "returncode": completed.returncode,
        "output": completed.stdout,
        "stderr": completed.stderr,
    }


def selected(path, names):
    wanted = set(names)
    lines = []
    for line in pathlib.Path(path).read_text(encoding="utf-8").splitlines():
        if line.split(maxsplit=1)[0].rstrip(":") in wanted:
            lines.append(line)
    return "\n".join(lines) + ("\n" if lines else "")


cgroup_path = "unavailable"
for line in pathlib.Path("/proc/self/cgroup").read_text(encoding="utf-8").splitlines():
    if line.startswith("0::"):
        cgroup_path = line[3:] or "/"
        break
cgroup_root = pathlib.Path("/sys/fs/cgroup") / cgroup_path.lstrip("/")

sysfs_fields = (
    "dev",
    "stat",
    "inflight",
    "device/model",
    "device/vendor",
    "device/queue_depth",
    "queue/scheduler",
    "queue/nr_requests",
    "queue/logical_block_size",
    "queue/physical_block_size",
    "queue/max_sectors_kb",
    "queue/max_hw_sectors_kb",
    "queue/read_ahead_kb",
    "queue/nomerges",
    "queue/rq_affinity",
    "queue/rotational",
    "queue/write_cache",
    "queue/fua",
    "queue/wbt_lat_usec",
    "queue/io_poll",
)
sysfs = {}
for device in devices:
    root = pathlib.Path("/sys/class/block") / device
    values = {field: read(root / field) for field in sysfs_fields}
    try:
        values["device_driver"] = str((root / "device/driver").resolve(strict=True)) + "\n"
    except OSError as error:
        values["device_driver"] = f"unavailable:{error.errno}\n"
    for queue in sorted((root / "mq").glob("*")):
        for field in ("cpu_list", "nr_tags", "nr_reserved_tags"):
            values[f"mq/{queue.name}/{field}"] = read(queue / field)
    sysfs[device] = values

nvme = {}
for controller in sorted(pathlib.Path("/sys/class/nvme").glob("nvme*")):
    if not controller.is_dir():
        continue
    values = {
        field: read(controller / field)
        for field in ("model", "serial", "firmware_rev", "state", "transport", "address")
    }
    for irq in sorted((controller / "device/msi_irqs").glob("*")):
        values[f"msi_irq/{irq.name}/smp_affinity_list"] = read(
            pathlib.Path("/proc/irq") / irq.name / "smp_affinity_list"
        )
    nvme[controller.name] = values

commands = {
    "hostname_f": command(["hostname", "-f"]),
    "uname": command(["uname", "-a"]),
    "uname_m": command(["uname", "-m"]),
    "nproc": command(["nproc", "--all"]),
    "lscpu": command(["lscpu"]),
    "compiler": command(["cc", "--version"]),
    "compiler_target": command(["cc", "-dumpmachine"]),
    "ldd": command(["ldd", "--version"]),
    "findmnt_data": command(["findmnt", "-J", "-T", data_directory]),
    "findmnt_tmp": command(["findmnt", "-J", "-T", "/tmp"]),
    "lsblk_all": command(
        [
            "lsblk",
            "-J",
            "-o",
            "NAME,KNAME,TYPE,MAJ:MIN,PKNAME,SIZE,ROTA,SCHED,MODEL,SERIAL,FSTYPE,MOUNTPOINTS",
        ]
    ),
    "lsblk_stack": command(
        [
            "lsblk",
            "-J",
            "-s",
            "-o",
            "NAME,KNAME,TYPE,MAJ:MIN,PKNAME,SIZE,ROTA,SCHED,MODEL,SERIAL",
            "/dev/" + filesystem_device,
        ]
    ),
    "virtualization": command(["systemd-detect-virt"]),
}
files = {
    "proc_cmdline": read("/proc/cmdline"),
    "proc_pressure_io": read("/proc/pressure/io"),
    "proc_diskstats": read("/proc/diskstats"),
    "proc_self_cgroup": read("/proc/self/cgroup"),
    "proc_aio_max_nr": read("/proc/sys/fs/aio-max-nr"),
    "proc_aio_nr": read("/proc/sys/fs/aio-nr"),
    "proc_meminfo_selected": selected(
        "/proc/meminfo", ("MemTotal", "MemAvailable", "Cached", "Dirty", "Writeback")
    ),
    "proc_vmstat_selected": selected(
        "/proc/vmstat",
        (
            "nr_dirty",
            "nr_writeback",
            "nr_dirty_threshold",
            "nr_dirty_background_threshold",
            "pgpgin",
            "pgpgout",
        ),
    ),
    "dmi_product_name": read("/sys/class/dmi/id/product_name"),
    "device_tree_model": read("/proc/device-tree/model"),
}
cgroup = {
    "path": cgroup_path,
    "files": {
        name: read(cgroup_root / name)
        for name in (
            "io.stat",
            "io.max",
            "io.weight",
            "io.pressure",
            "io.cost.qos",
            "io.cost.model",
            "io.latency",
        )
    },
}
value = {
    "schema": "topic53-host.v1",
    "target_label": target_label,
    "expected_hostname": expected_hostname,
    "expected_architecture": expected_architecture,
    "runtime_hostname": runtime_hostname,
    "runtime_architecture": runtime_architecture,
    "source_commit": source_commit,
    "source_archive_sha256": source_archive_sha256,
    "page_size": os.sysconf("SC_PAGE_SIZE"),
    "allowed_affinity": sorted(os.sched_getaffinity(0)),
    "data_parent": data_parent,
    "filesystem_source": filesystem_source,
    "filesystem_fstype": filesystem_fstype,
    "filesystem_major_minor": filesystem_major_minor,
    "stack_devices": devices,
    "primary_device": primary_device,
    "commands": commands,
    "files": files,
    "sysfs": sysfs,
    "nvme": nvme,
    "cgroup": cgroup,
}
pathlib.Path(output_path).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

probe_source=$topic_dir/experiment/nvme_aio_depth_probe.c
binary=$receipt/bin/nvme_aio_depth_probe
compile_flags=(
    -O3 -g -fno-omit-frame-pointer -march=native -std=gnu11
    -Wall -Wextra -Werror
)
compile_argv=(cc "${compile_flags[@]}" "$probe_source" -o "$binary")
set +e
"${compile_argv[@]}" \
    >"$receipt/build/compile.stdout" 2>"$receipt/build/compile.stderr"
compile_status=$?
set -e
python3 -I -B - \
    "$receipt/build/compile.status.json" "$compile_status" \
    "$receipt/build/compile.stdout" "$receipt/build/compile.stderr" \
    "${compile_argv[@]}" <<'PY'
import hashlib
import json
import pathlib
import sys

path, returncode, stdout, stderr, *argv = sys.argv[1:]


def sha256(name):
    return hashlib.sha256(pathlib.Path(name).read_bytes()).hexdigest()


value = {
    "schema": "topic53-command-status.v1",
    "argv": argv,
    "returncode": int(returncode),
    "stdout_sha256": sha256(stdout),
    "stderr_sha256": sha256(stderr),
}
pathlib.Path(path).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
if ((compile_status != 0)); then
    printf 'native compilation failed\n' >&2
    exit 1
fi

source_sha256=$(sha256sum -- "$probe_source" | awk '{print $1}')
binary_sha256=$(sha256sum -- "$binary" | awk '{print $1}')
printf '%s  nvme_aio_depth_probe\n' "$binary_sha256" \
    >"$receipt/bin/nvme_aio_depth_probe.sha256"
cc --version >"$receipt/build/compiler-version.txt"
compiler_path=$(readlink -f -- "$(command -v cc)")
compiler_version_sha256=$(sha256sum -- "$receipt/build/compiler-version.txt" | awk '{print $1}')
compiler_target=$(cc -dumpmachine)
compile_argv_json=$(python3 -I -B - "${compile_argv[@]}" <<'PY'
import json
import sys
print(json.dumps(sys.argv[1:], separators=(",", ":")))
PY
)
{
    printf 'source_sha256=%s\n' "$source_sha256"
    printf 'binary_sha256=%s\n' "$binary_sha256"
    printf 'compiler_path=%s\n' "$compiler_path"
    printf 'compiler_version_sha256=%s\n' "$compiler_version_sha256"
    printf 'compiler_target=%s\n' "$compiler_target"
    printf 'compile_argv_json=%s\n' "$compile_argv_json"
} >"$receipt/build/identity.txt"

file -- "$binary" >"$receipt/bin/file.txt"
ldd -- "$binary" >"$receipt/bin/ldd.txt" 2>&1
readelf -h -n -- "$binary" >"$receipt/bin/readelf.txt"
nm -n -- "$binary" >"$receipt/codegen/symbols.txt"
cc "${compile_flags[@]}" -S "$probe_source" -o "$receipt/codegen/probe.s"
objdump -drwC --no-show-raw-insn -- "$binary" >"$receipt/codegen/all.asm"
objdump -drwC --no-show-raw-insn --disassemble=cached_read_loop -- "$binary" \
    >"$receipt/codegen/cached_read_loop.asm"
objdump -drwC --no-show-raw-insn --disassemble=direct_aio_loop -- "$binary" \
    >"$receipt/codegen/direct_aio_loop.asm"
rg -q 'cached_read_loop' "$receipt/codegen/symbols.txt"
rg -q 'direct_aio_loop' "$receipt/codegen/symbols.txt"
rg -q 'cached_read_loop' "$receipt/codegen/cached_read_loop.asm"
rg -q 'direct_aio_loop' "$receipt/codegen/direct_aio_loop.asm"

run_control() {
    local name=$1
    shift
    local stdout=$receipt/controls/$name.stdout
    local stderr=$receipt/controls/$name.stderr
    local status_path=$receipt/controls/$name.status.json
    local returncode
    set +e
    "$@" >"$stdout" 2>"$stderr"
    returncode=$?
    set -e
    python3 -I -B - "$status_path" "$name" "$returncode" "$stdout" "$stderr" "$@" <<'PY'
import hashlib
import json
import pathlib
import sys

path, name, returncode, stdout, stderr, *argv = sys.argv[1:]


def sha256(filename):
    return hashlib.sha256(pathlib.Path(filename).read_bytes()).hexdigest()


value = {
    "schema": "topic53-control-status.v1",
    "name": name,
    "argv": argv,
    "returncode": int(returncode),
    "stdout_sha256": sha256(stdout),
    "stderr_sha256": sha256(stderr),
}
pathlib.Path(path).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY
    if ((returncode != 0)); then
        printf 'control failed: %s\n' "$name" >&2
        exit 1
    fi
    if [[ -s $stderr ]]; then
        printf 'control wrote stderr: %s\n' "$name" >&2
        exit 1
    fi
}

run_control init "$binary" init "$data_file" 128
run_control verify "$binary" verify "$data_file"
run_control smoke-q1 "$binary" run "$data_file" direct 256 1 530001 smoke-q1
run_control smoke-q8 "$binary" run "$data_file" direct 256 8 530001 smoke-q8

python3 -I -B "$topic_dir/experiment/run_processes.py" \
    --binary "$binary" --source "$probe_source" --data "$data_file" \
    --output "$receipt/campaign/depth" --scenario depth \
    --devices "$devices_csv" --primary-device "$primary_device" \
    --ops "$ops" --file-bytes 134217728
python3 -I -B "$topic_dir/experiment/run_processes.py" \
    --binary "$binary" --source "$probe_source" --data "$data_file" \
    --output "$receipt/campaign/aa" --scenario aa \
    --devices "$devices_csv" --primary-device "$primary_device" \
    --ops "$ops" --file-bytes 134217728
python3 -I -B "$topic_dir/experiment/analyze.py" "$receipt/campaign" \
    >"$receipt/campaign/summary.json"

write_source_manifest "$receipt/source/source-files-after.sha256"
cmp -- "$receipt/source/source-files-before.sha256" \
    "$receipt/source/source-files-after.sha256"

rm -f -- "$data_file"
rmdir -- "$data_dir"
data_live=0
python3 -I -B - "$receipt/cleanup.json" <<'PY'
import json
import pathlib
import sys

value = {
    "schema": "topic53-cleanup.v1",
    "removed_files": ["data.bin"],
    "data_directory_removed": True,
}
pathlib.Path(sys.argv[1]).write_text(
    json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
)
PY

preseal_validation=$(mktemp /tmp/topic53-preseal.XXXXXXXX.json)
final_validation=$(mktemp /tmp/topic53-final.XXXXXXXX.json)
python3 -I -B "$topic_dir/experiment/validate_receipt.py" "$receipt" \
    --expected-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-commit "$SOURCE_COMMIT" \
    --expected-archive-sha256 "$SOURCE_ARCHIVE_SHA256" \
    --allow-unsealed >"$preseal_validation"
install -m 0444 -- "$preseal_validation" "$receipt/receipt-validation.json"
rm -f -- "$preseal_validation"

manifest_tmp=$source_work/MANIFEST.sha256
(
    cd "$receipt"
    mapfile -t receipt_files < <(
        rg --files --hidden --no-ignore | \
            rg -v '^(MANIFEST\.sha256|SEALED)$' | LC_ALL=C sort
    )
    if ((${#receipt_files[@]} == 0)); then
        printf 'receipt enumeration returned no files\n' >&2
        exit 1
    fi
    sha256sum -- "${receipt_files[@]}" >"$manifest_tmp"
)
install -m 0444 -- "$manifest_tmp" "$receipt/MANIFEST.sha256"
printf 'topic53-receipt.v1\n' >"$receipt/SEALED"
chmod -R a-w -- "$receipt"

python3 -I -B "$topic_dir/experiment/validate_receipt.py" "$receipt" \
    --expected-label "$target_label" \
    --expected-hostname "$expected_hostname" \
    --expected-architecture "$expected_architecture" \
    --expected-commit "$SOURCE_COMMIT" \
    --expected-archive-sha256 "$SOURCE_ARCHIVE_SHA256" \
    >"$final_validation"
cat "$final_validation"
rm -f -- "$final_validation"

rm -rf -- "$source_work"
source_live=0
trap - EXIT
printf 'sealed Topic 53 receipt: %s\n' "$receipt"
