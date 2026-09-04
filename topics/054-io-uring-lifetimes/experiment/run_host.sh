#!/usr/bin/env bash
set -euo pipefail
export LANG=C
export LC_ALL=C
export TZ=UTC

receipt=${1:?receipt directory required}
archive=${2:?source archive required}
target_label=${3:?target label required}
expected_hostname=${4:?expected hostname required}
expected_architecture=${5:?expected architecture required}
source_commit=${6:?source commit required}
expected_archive_sha256=${7:?source archive SHA-256 required}

test ! -e "$receipt"
test -f "$archive"
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]]
[[ "$expected_archive_sha256" =~ ^[0-9a-f]{64}$ ]]

actual_archive_sha256=$(sha256sum "$archive" | awk '{print $1}')
test "$actual_archive_sha256" = "$expected_archive_sha256"

actual_hostname=$(hostname -f)
actual_architecture=$(uname -m)
test "$actual_hostname" = "$expected_hostname"
test "$actual_architecture" = "$expected_architecture"

work=$(mktemp -d "/var/tmp/topic54-io-uring-${source_commit:0:7}.XXXXXX")
cleanup_work() {
    chmod -R u+w "$work" 2>/dev/null || true
    rm -r -- "$work"
}
trap cleanup_work EXIT

trusted_archive="$work/source.tar.gz"
cp "$archive" "$trusted_archive"
test "$(sha256sum "$trusted_archive" | awk '{print $1}')" = "$expected_archive_sha256"
chmod a-w "$trusted_archive"

python3 - "$trusted_archive" "$source_commit" <<'PY'
import os
import sys
import tarfile
from pathlib import PurePosixPath

archive, commit = sys.argv[1:]
root = f"systems-snackpack-{commit}"
topic = f"{root}/topics/054-io-uring-lifetimes"
ancestors = {root, f"{root}/topics", topic}
required = {
    f"{topic}/experiment/io_uring_lifetimes.c",
    f"{topic}/experiment/run_host.sh",
}
names = set()
regular_files = set()
total_size = 0

if os.path.getsize(archive) > 16 * 1024 * 1024:
    raise SystemExit("archive exceeds the compressed size bound")

with tarfile.open(archive, "r:gz") as bundle:
    if bundle.pax_headers.get("comment") != commit:
        raise SystemExit("archive lacks the expected Git commit header")
    members = bundle.getmembers()
    if not members or len(members) > 96:
        raise SystemExit("archive member count is outside the safe bound")
    for member in members:
        name = member.name.rstrip("/")
        pure = PurePosixPath(name)
        if (
            not name
            or pure.is_absolute()
            or ".." in pure.parts
            or name in names
            or (name not in ancestors and not name.startswith(topic + "/"))
        ):
            raise SystemExit(f"unsafe or duplicate archive member: {member.name!r}")
        names.add(name)
        if member.isdir():
            continue
        if name in ancestors or not member.isfile() or member.size > 2 * 1024 * 1024:
            raise SystemExit(f"unsupported or oversized archive member: {member.name!r}")
        total_size += member.size
        regular_files.add(name)
    if total_size > 16 * 1024 * 1024:
        raise SystemExit("archive expands beyond the safe size bound")
    if not regular_files or len(regular_files) > 64:
        raise SystemExit("archive topic file count is outside the safe bound")
    if not required.issubset(regular_files):
        raise SystemExit("archive lacks the exact runner or native probe")
PY

tar -xzf "$trusted_archive" -C "$work"

mkdir -m 0700 "$receipt"
mkdir "$receipt/results" "$receipt/codegen"

source_root="$work/systems-snackpack-$source_commit"
topic_root="$source_root/topics/054-io-uring-lifetimes"
source_file="$topic_root/experiment/io_uring_lifetimes.c"
archived_runner="$topic_root/experiment/run_host.sh"
test -f "$source_file"
test -f "$archived_runner"

if ! cmp -s "${BASH_SOURCE[0]}" "$archived_runner"; then
    printf 'error: %s differs from the archived launcher at %s\n' \
        "${BASH_SOURCE[0]}" "$source_commit" >&2
    exit 1
fi
runner_sha256=$(sha256sum "$archived_runner" | awk '{print $1}')

cp "$trusted_archive" "$receipt/source.tar.gz"
cp "$source_file" "$receipt/io_uring_lifetimes.c"

(
    cd "$source_root"
    rg --files -0 topics/054-io-uring-lifetimes \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "$receipt/source-files-before.sha256"

{
    printf 'target_label=%s\n' "$target_label"
    printf 'hostname=%s\n' "$actual_hostname"
    printf 'architecture=%s\n' "$actual_architecture"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$actual_archive_sha256"
    printf 'runner_sha256=%s\n' "$runner_sha256"
    printf 'run_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} > "$receipt/identity.txt"

{
    uname -a
    getconf _NPROCESSORS_ONLN
    lscpu
    cc --version
    cc -dumpmachine
    rustc --version --verbose || printf 'rustc=absent\n'
    printf 'memlock_kib=%s\n' "$(ulimit -l)"
    if [[ -r /proc/sys/kernel/io_uring_disabled ]]; then
        printf 'kernel.io_uring_disabled='
        cat /proc/sys/kernel/io_uring_disabled
    else
        printf 'kernel.io_uring_disabled=absent\n'
    fi
} > "$receipt/host.txt" 2>&1

build_flags=(-O2 -g -std=c11 -Wall -Wextra -Werror -pthread)
{
    printf 'build_command=cc %s io_uring_lifetimes.c -o io_uring_lifetimes\n' \
        "${build_flags[*]}"
    cc "${build_flags[@]}" "$source_file" -o "$receipt/io_uring_lifetimes"
    cc "${build_flags[@]}" -S "$source_file" \
        -o "$receipt/codegen/io_uring_lifetimes.s"
    sha256sum "$source_file" "$receipt/io_uring_lifetimes"
} > "$receipt/build.txt" 2>&1

objdump -dr "$receipt/io_uring_lifetimes" \
    > "$receipt/codegen/objdump.txt"
rg -n 'syscall|io_uring|IORING|ring_(setup|enter|submit|wait)' \
    "$receipt/codegen/io_uring_lifetimes.s" \
    "$receipt/codegen/objdump.txt" \
    > "$receipt/codegen/retained-paths.txt"
rg -q '\b(call|callq|bl|blr)\b.*<syscall(@plt)?>' \
    "$receipt/codegen/objdump.txt"

for repetition in 1 2; do
    timeout 10s "$receipt/io_uring_lifetimes" \
        > "$receipt/results/run-$repetition.txt"

    output="$receipt/results/run-$repetition.txt"
    test "$(wc -l < "$output")" -eq 5
    rg -q '^baseline_setup=ok sq_entries=8 cq_entries=16 features=0x[0-9a-f]+$' "$output"
    rg -q '^single_issuer owner_cqe=\{user_data=0x1001,res=0\} other_task_enter=-17 \(File exists\)$' "$output"
    rg -q '^defer_taskrun cqes_before_getevents=0 terminal=\{user_data=0x2001,res=-62\}$' "$output"
    rg -q '^cancel terminal_1=.*terminal_2=.*$' "$output"
    rg -q 'user_data=0x3001,res=-125' "$output"
    rg -q 'user_data=0x3002,res=0' "$output"
    rg -q '^result=ok$' "$output"

    {
        rg '^(baseline_setup|single_issuer|defer_taskrun|result=)' "$output"
        rg -o 'user_data=0x300[12],res=-?[0-9]+' "$output" | LC_ALL=C sort
    } > "$receipt/results/run-$repetition-normalized.txt"
done

cmp "$receipt/results/run-1-normalized.txt" \
    "$receipt/results/run-2-normalized.txt"
printf '%s\n' 'aa_control=pass normalized semantic outputs match' \
    > "$receipt/results/aa-control.txt"

(
    cd "$source_root"
    rg --files -0 topics/054-io-uring-lifetimes \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "$receipt/source-files-after.sha256"
cmp "$receipt/source-files-before.sha256" "$receipt/source-files-after.sha256"

{
    printf 'run=pass\n'
    printf 'process_repetitions=2\n'
    printf 'timing_claim=no\n'
    printf 'storage_tested=no\n'
    printf 'sqpoll_tested=no\n'
    printf 'iopoll_tested=no\n'
    printf 'registered_resources_tested=no\n'
    printf 'multishot_tested=no\n'
} > "$receipt/run-status.txt"

manifest_tmp="$work/MANIFEST.sha256"
(
    cd "$receipt"
    rg --files -0 | LC_ALL=C sort -z | xargs -0 sha256sum
) > "$manifest_tmp"
mv "$manifest_tmp" "$receipt/MANIFEST.sha256"
touch "$receipt/SEALED"
chmod -R a-w "$receipt"

trap - EXIT
cleanup_work
printf 'run=pass receipt=%s\n' "$receipt"
