#!/usr/bin/env bash
set -euo pipefail

receipt=${1:?receipt directory required}
archive=${2:?source archive required}
target_label=${3:?target label required}
expected_hostname=${4:?expected hostname required}
expected_architecture=${5:?expected architecture required}
source_commit=${6:?source commit required}
expected_archive_sha256=${7:?source archive SHA-256 required}

test ! -e "$receipt"
test -f "$archive"

actual_archive_sha256=$(sha256sum "$archive" | awk '{print $1}')
test "$actual_archive_sha256" = "$expected_archive_sha256"

actual_hostname=$(hostname -f)
actual_architecture=$(uname -m)
test "$actual_hostname" = "$expected_hostname"
test "$actual_architecture" = "$expected_architecture"

work=$(mktemp -d "/var/tmp/topic52-cow-${source_commit:0:7}.XXXXXX")
cleanup_work() {
    chmod -R u+w "$work" 2>/dev/null || true
    rm -r -- "$work"
}
trap cleanup_work EXIT

mkdir -m 0700 "$receipt"
mkdir "$receipt/results" "$receipt/codegen"
tar -xzf "$archive" -C "$work"

source_root="$work/systems-snackpack-$source_commit"
source_file="$source_root/topics/052-filesystem-crash-semantics/experiment/cow_crash_probe.c"
test -f "$source_file"

cp "$archive" "$receipt/source.tar.gz"
cp "$source_file" "$receipt/cow_crash_probe.c"

(
    cd "$source_root"
    rg --files -0 topics/052-filesystem-crash-semantics \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "$receipt/source-files-before.sha256"

{
    printf 'target_label=%s\n' "$target_label"
    printf 'hostname=%s\n' "$actual_hostname"
    printf 'architecture=%s\n' "$actual_architecture"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$actual_archive_sha256"
    printf 'run_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} > "$receipt/identity.txt"

{
    uname -a
    nproc
    lscpu
    cc --version
    cc -dumpmachine
    rustc --version --verbose
} > "$receipt/host.txt" 2>&1

{
    findmnt -T "$work" -o TARGET,SOURCE,FSTYPE,OPTIONS
    stat -f -c 'type=%T block=%S namelen=%l' "$work"
    df -B1 "$work"
    lsblk -o NAME,TYPE,SIZE,FSTYPE,MOUNTPOINTS
    xfs_info "$work" 2>&1 || true
} > "$receipt/filesystem.txt"

build_flags=(-O2 -g -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer)
{
    printf 'build_command=cc %s cow_crash_probe.c -o cow_crash_probe\n' "${build_flags[*]}"
    cc "${build_flags[@]}" "$source_file" -o "$receipt/cow_crash_probe"
    cc "${build_flags[@]}" -S "$source_file" -o "$receipt/codegen/cow_crash_probe.s"
    sha256sum "$source_file" "$receipt/cow_crash_probe"
} > "$receipt/build.txt" 2>&1

objdump -dr "$receipt/cow_crash_probe" > "$receipt/codegen/objdump.txt"
rg -n 'openat|fsync|renameat|fnv1a' \
    "$receipt/codegen/cow_crash_probe.s" \
    "$receipt/codegen/objdump.txt" > "$receipt/codegen/retained-paths.txt"

"$receipt/cow_crash_probe" model > "$receipt/results/model.txt"

for cut in after_write after_file_fsync after_rename after_dir_fsync; do
    case_dir="$work/case-$cut"
    mkdir "$case_dir"
    "$receipt/cow_crash_probe" init "$case_dir" > "$receipt/results/$cut-init.txt"
    set +e
    "$receipt/cow_crash_probe" update "$case_dir" "$cut" \
        > "$receipt/results/$cut-update.txt" 2>&1
    update_status=$?
    set -e
    case "$cut" in
        after_write) expected_status=101 ;;
        after_file_fsync) expected_status=102 ;;
        after_rename) expected_status=103 ;;
        after_dir_fsync) expected_status=104 ;;
    esac
    printf 'cut=%s update_exit=%d expected_exit=%d\n' \
        "$cut" "$update_status" "$expected_status" \
        > "$receipt/results/$cut-status.txt"
    test "$update_status" -eq "$expected_status"

    "$receipt/cow_crash_probe" verify "$case_dir" \
        > "$receipt/results/$cut-verify.txt"
    if [[ "$cut" = after_write || "$cut" = after_file_fsync ]]; then
        rg -q '^verify current=OLD temp=present magic=valid checksum=valid generation=41$' \
            "$receipt/results/$cut-verify.txt"
    else
        rg -q '^verify current=NEW temp=absent magic=valid checksum=valid generation=42$' \
            "$receipt/results/$cut-verify.txt"
    fi
done

for repetition in 1 2; do
    case_dir="$work/case-complete-$repetition"
    mkdir "$case_dir"
    "$receipt/cow_crash_probe" init "$case_dir" \
        > "$receipt/results/complete-$repetition-init.txt"
    "$receipt/cow_crash_probe" update "$case_dir" none \
        > "$receipt/results/complete-$repetition-update.txt"
    "$receipt/cow_crash_probe" verify "$case_dir" \
        > "$receipt/results/complete-$repetition-verify.txt"
    rg '^verify ' "$receipt/results/complete-$repetition-verify.txt" \
        > "$receipt/results/complete-$repetition-oracle.txt"
done
cmp "$receipt/results/complete-1-oracle.txt" \
    "$receipt/results/complete-2-oracle.txt"
printf '%s\n' 'aa_control=pass complete verifier outputs match' \
    > "$receipt/results/aa-control.txt"

corrupt_dir="$work/case-corrupt-control"
mkdir "$corrupt_dir"
"$receipt/cow_crash_probe" init "$corrupt_dir" \
    > "$receipt/results/corrupt-init.txt"
"$receipt/cow_crash_probe" update "$corrupt_dir" none \
    > "$receipt/results/corrupt-update.txt"
"$receipt/cow_crash_probe" corrupt "$corrupt_dir" \
    > "$receipt/results/corrupt-action.txt"
set +e
"$receipt/cow_crash_probe" verify "$corrupt_dir" \
    > "$receipt/results/corrupt-verify.txt" 2>&1
corrupt_status=$?
set -e
printf 'corrupt_verify_exit=%d expected_exit=3\n' "$corrupt_status" \
    > "$receipt/results/corrupt-status.txt"
test "$corrupt_status" -eq 3
rg -q '^verify current=INVALID .* checksum=invalid generation=42$' \
    "$receipt/results/corrupt-verify.txt"

reflink_dir="$work/case-reflink-control"
mkdir "$reflink_dir"
cp --reflink=always "$work/case-complete-1/current" "$reflink_dir/current" \
    > "$receipt/results/reflink.txt" 2>&1
cmp "$work/case-complete-1/current" "$reflink_dir/current"
filefrag -v "$work/case-complete-1/current" "$reflink_dir/current" \
    > "$receipt/results/reflink-before-filefrag.txt" 2>&1 || true
"$receipt/cow_crash_probe" corrupt "$reflink_dir" \
    > "$receipt/results/reflink-corrupt-clone.txt"
set +e
"$receipt/cow_crash_probe" verify "$reflink_dir" \
    > "$receipt/results/reflink-clone-verify.txt" 2>&1
reflink_clone_status=$?
cmp "$work/case-complete-1/current" "$reflink_dir/current"
reflink_cmp_status=$?
set -e
test "$reflink_clone_status" -eq 3
test "$reflink_cmp_status" -ne 0
"$receipt/cow_crash_probe" verify "$work/case-complete-1" \
    > "$receipt/results/reflink-source-verify.txt"
filefrag -v "$work/case-complete-1/current" "$reflink_dir/current" \
    > "$receipt/results/reflink-after-filefrag.txt" 2>&1 || true
{
    printf 'reflink_copy=success\n'
    printf 'reflink_clone_verify_exit=%d expected_exit=3\n' "$reflink_clone_status"
    printf 'reflink_post_write_cmp_exit=%d expected_nonzero=yes\n' "$reflink_cmp_status"
    printf '%s\n' 'boundary=range-level clone isolation only; not crash recovery or whole-tree CoW evidence'
} >> "$receipt/results/reflink.txt"

(
    cd "$source_root"
    rg --files -0 topics/052-filesystem-crash-semantics \
        | LC_ALL=C sort -z \
        | xargs -0 sha256sum
) > "$receipt/source-files-after.sha256"
cmp "$receipt/source-files-before.sha256" "$receipt/source-files-after.sha256"

{
    printf 'run=pass\n'
    printf 'process_crash_only=yes\n'
    printf 'power_loss_tested=no\n'
    printf 'filesystem_replay_tested=no\n'
    printf 'timing_claim=no\n'
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
