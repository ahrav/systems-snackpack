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
    printf 'Topic 50 host receipts require Linux\n' >&2
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
arm_target=dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com

if [[ ! $source_commit =~ ^[0-9a-f]{40}$ || ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'source commit or archive digest has the wrong shape\n' >&2
    exit 2
fi
if [[ ! -f $SOURCE_ARCHIVE_PATH ]]; then
    printf 'SOURCE_ARCHIVE_PATH is not a regular file\n' >&2
    exit 2
fi
source_archive_input=$(realpath -- "$SOURCE_ARCHIVE_PATH")
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
        if [[ $expected_hostname != "$arm_target" || $architecture != aarch64 || \
            $expected_architecture != aarch64 ]]; then
            printf 'literal Arm target identity or architecture changed\n' >&2
            exit 2
        fi
        ;;
    *)
        printf 'unauthorized Topic 50 target label: %s\n' "$target_label" >&2
        exit 2
        ;;
esac

actual_archive_sha256=$(sha256sum -- "$source_archive_input" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$source_archive_sha256" ]]; then
    printf 'uploaded source archive digest mismatch\n' >&2
    exit 2
fi

private_dir=$(mktemp -d)
source_tree=$(mktemp -d)
preseal_validation="$private_dir/preseal-validation.json"
final_validation="$private_dir/final-validation.json"
trap 'rm -rf -- "$private_dir" "$source_tree"' EXIT

mkdir -p -- "$output_dir"
install -m 0400 -- "$source_archive_input" "$output_dir/source-archive.tar.gz"
python3 -I -B - "$output_dir/source-archive.tar.gz" "$source_commit" <<'PY'
import pathlib
import sys
import tarfile

archive_path = pathlib.Path(sys.argv[1])
commit = sys.argv[2]
prefix = f"systems-snackpack-{commit}/"
topic = prefix + "topics/050-cpu-service-chain/"
ancestors = {prefix.rstrip("/"), prefix + "topics", topic.rstrip("/")}
required = {
    topic + "experiment/README.md",
    topic + "experiment/lock_holder_preemption.c",
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
    if len(members) > 256:
        raise SystemExit("source archive exceeds 256 members")
    seen = set()
    normalized = set()
    files = set()
    total = 0
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
        if member.name != prefix.rstrip("/") and not member.name.startswith(prefix):
            raise SystemExit(f"archive member escaped unique prefix: {member.name}")
        if member.isfile() and not member.name.startswith(topic):
            raise SystemExit(f"archive is not path-limited to Topic 50: {member.name}")
        if member.isdir() and member.name.rstrip("/") not in ancestors and not member.name.startswith(topic):
            raise SystemExit(f"archive directory escaped Topic 50 ancestors: {member.name}")
        seen.add(member.name)
        normalized.add(str(path))
        if member.isfile():
            files.add(member.name)
            total += member.size
    if not required.issubset(files):
        raise SystemExit(f"archive lacks required experiment files: {sorted(required - files)}")
    if len(files) > 128 or total > 16 * 1024 * 1024:
        raise SystemExit("source archive exceeds file-count or uncompressed-byte cap")
PY

tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_tree"
runner_relative=topics/050-cpu-service-chain/experiment/run_host.sh
mapfile -t archived_runners < <(
    rg --files --hidden --no-ignore "$source_tree" | rg "/${runner_relative}$" | LC_ALL=C sort
)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 50 runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/050-cpu-service-chain/experiment"
if ! cmp -s -- "${BASH_SOURCE[0]}" "$archive_script_dir/run_host.sh"; then
    printf 'executing host runner differs from archived runner\n' >&2
    exit 2
fi
case $output_dir/ in
    "$archive_repo_root"/*)
        printf 'write host receipts outside the extracted source tree\n' >&2
        exit 2
        ;;
esac

write_source_manifest() {
    local destination=$1
    (
        cd "$archive_repo_root"
        mapfile -t paths < <(
            rg --files topics/050-cpu-service-chain/experiment | LC_ALL=C sort
        )
        if ((${#paths[@]} == 0)); then
            # An empty expansion would leave sha256sum reading stdin forever.
            printf 'source manifest found no experiment files\n' >&2
            exit 2
        fi
        sha256sum -- "${paths[@]}"
    ) >"$destination"
}

write_source_manifest "$output_dir/source-manifest-before.sha256"
install -m 0400 -- "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-files.sha256"

if ! cc --version | head -n 1 | rg -qi 'gcc'; then
    printf 'Topic 50 exact codegen contract requires GCC on the authorized hosts\n' >&2
    exit 2
fi

python3 -I -B - "$output_dir/host.json" "$target_label" "$expected_hostname" \
    "$expected_architecture" "$source_commit" "$source_archive_sha256" <<'PY'
import json
import os
import pathlib
import platform
import subprocess
import sys

output, label, expected_host, expected_arch, commit, archive_sha = sys.argv[1:]
def command(argv):
    process = subprocess.run(argv, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return {"argv": argv, "returncode": process.returncode, "output": process.stdout.strip()}
value = {
    "schema": "topic50-host.v1",
    "target_label": label,
    "expected_hostname": expected_host,
    "expected_architecture": expected_arch,
    "runtime_hostname": command(["hostname", "-f"]),
    "uname": command(["uname", "-a"]),
    "machine": platform.machine(),
    "kernel_release": platform.release(),
    "source_commit": commit,
    "source_archive_sha256": archive_sha,
    "configured_cpu_count": os.cpu_count(),
    "allowed_affinity": sorted(os.sched_getaffinity(0)),
    "lscpu": command(["lscpu", "-J"]),
}
pathlib.Path(output).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

{
    printf '[compiler]\n'
    cc --version
    printf '[python]\n'
    python3 --version
    printf '[build-command]\n'
    printf 'cc -O2 -g -std=c11 -Wall -Wextra -Werror -pthread %s -o %s\n' \
        "$archive_script_dir/lock_holder_preemption.c" \
        "$output_dir/experiment/lock_holder_preemption"
} >"$output_dir/build.txt"

SOURCE_COMMIT="$source_commit" \
SOURCE_ARCHIVE_SHA256="$source_archive_sha256" \
TOPIC50_TARGET_LABEL="$target_label" \
TOPIC50_EXPECTED_HOSTNAME="$expected_hostname" \
TOPIC50_EXPECTED_ARCHITECTURE="$expected_architecture" \
python3 -I -B "$archive_script_dir/run_processes.py" "$output_dir/experiment" \
    >"$output_dir/campaign.txt"

python3 -I -B "$archive_script_dir/analyze.py" "$output_dir/experiment" \
    >"$output_dir/experiment/summary.json"

binary="$output_dir/experiment/lock_holder_preemption"
sha256sum -- "$binary" >"$output_dir/binary.sha256"
file -- "$binary" >"$output_dir/binary.file.txt"
ldd -- "$binary" >"$output_dir/binary.ldd.txt"
readelf -nW -- "$binary" >"$output_dir/binary.build-id.txt"

mkdir -- "$output_dir/codegen"
objdump -drwC --no-show-raw-insn -- "$binary" >"$output_dir/codegen/all.asm"
nm -an -- "$binary" >"$output_dir/codegen/symbols.txt"
for symbol in holder_main waiter_main hog_main burn_thread_cpu; do
    objdump -drwC --no-show-raw-insn --disassemble="$symbol" -- "$binary" \
        >"$output_dir/codegen/$symbol.asm"
done

mapfile -t selected < <(
    python3 -I -B - "$output_dir/experiment/metadata.json" <<'PY'
import json
import pathlib
import sys
value = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding="utf-8"))
selected = value["selected"]
print(selected["holder"])
print(selected["waiter"])
print(selected["control"])
PY
)
if [[ ${#selected[@]} -ne 3 ]]; then
    printf 'campaign metadata did not expose three selected CPUs\n' >&2
    exit 2
fi
holder_cpu=${selected[0]}
waiter_cpu=${selected[1]}
control_cpu=${selected[2]}
mkdir -- "$output_dir/smoke"
run_smoke() {
    local name=$1
    local mode=$2
    local hog_cpu=$3
    local stdout="$output_dir/smoke/$name.stdout"
    local stderr="$output_dir/smoke/$name.stderr"
    local started_ns ended_ns returncode
    started_ns=$(date +%s%N)
    set +e
    "$binary" smoke 0 0 "$mode" "$holder_cpu" "$waiter_cpu" "$hog_cpu" 19 5000 \
        >"$stdout" 2>"$stderr"
    returncode=$?
    set -e
    ended_ns=$(date +%s%N)
    python3 -I -B - "$output_dir/smoke/$name.status.json" "$name" "$mode" \
        "$hog_cpu" "$started_ns" "$ended_ns" "$returncode" <<'PY'
import json
import pathlib
import sys
path, name, mode, hog, started, ended, returncode = sys.argv[1:]
value = {
    "schema": "topic50-smoke.v1", "name": name, "mode": mode,
    "hog_cpu": int(hog), "started_realtime_ns": int(started),
    "ended_realtime_ns": int(ended), "returncode": int(returncode),
}
pathlib.Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
    if [[ $returncode -ne 0 ]]; then
        printf 'smoke %s failed with status %s\n' "$name" "$returncode" >&2
        exit 2
    fi
}
run_smoke same-cpu same_cpu "$holder_cpu"
run_smoke separate-core separate_core "$control_cpu"

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff" || {
    printf 'archived Topic 50 source mutated during execution\n' >&2
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
for path in sorted(root.rglob("*")):
    relative = path.relative_to(root).as_posix()
    mode = path.lstat().st_mode
    if stat.S_ISLNK(mode):
        raise SystemExit(f"receipt contains a symbolic link: {relative}")
    if stat.S_ISREG(mode):
        if relative in excluded:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{digest}  {relative}")
    elif not stat.S_ISDIR(mode):
        raise SystemExit(f"receipt contains a special entry: {relative}")
PY
manifest_sha256=$(sha256sum -- "$output_dir/MANIFEST.sha256" | awk '{print $1}')
manifest_file_count=$(wc -l <"$output_dir/MANIFEST.sha256")
python3 -I -B - "$output_dir/SEALED" "$manifest_sha256" "$manifest_file_count" \
    "$source_commit" "$target_label" <<'PY'
import json
import pathlib
import sys
path, digest, count, commit, target = sys.argv[1:]
value = {
    "schema": "topic50-seal.v1", "manifest_sha256": digest,
    "manifest_file_count": int(count), "source_commit": commit, "target_label": target,
}
pathlib.Path(path).write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
PY
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
printf 'Topic 50 sealed receipt: %s\n' "$output_dir"
