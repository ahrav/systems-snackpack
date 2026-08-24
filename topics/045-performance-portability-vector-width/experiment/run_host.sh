#!/usr/bin/env bash
set -euo pipefail

export PYTHONDONTWRITEBYTECODE=1
unset BASH_ENV CDPATH ENV GLOBIGNORE LD_PRELOAD PYTHONHOME PYTHONPATH

if [[ $# -lt 1 || $# -gt 3 ]]; then
    printf 'usage: %s OUTPUT_DIR [CPU] [STEPS]\n' "$0" >&2
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 45 host receipts require Linux\n' >&2
    exit 2
fi
: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the source archive digest}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to the authorized target label}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the resolved hostname}"

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
pax_header=$(gzip -dc -- "$source_archive" 2>/dev/null | \
    dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_header =~ comment=([0-9a-f]{40}) || ${BASH_REMATCH[1]} != "$SOURCE_COMMIT" ]]; then
    printf 'source archive does not embed commit %s\n' "$SOURCE_COMMIT" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(cd -- "$script_dir/../../.." && pwd -P)
output_dir=$(realpath -m -- "$1")
cpu=${2:-$(python3 -I -B -c 'import os; print(min(os.sched_getaffinity(0)))')}
steps=${3:-20000000}
warmup_steps=2000000
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
        printf 'unauthorized Topic 45 target: %s\n' "$SSH_TARGET_LABEL" >&2
        exit 2
        ;;
esac
if [[ -e $output_dir ]]; then
    printf 'output path already exists: %s\n' "$output_dir" >&2
    exit 2
fi
case $output_dir in
    "$repo_root" | "$repo_root"/*)
        printf 'write host receipts outside the repository\n' >&2
        exit 2
        ;;
esac
if [[ ! $cpu =~ ^[0-9]+$ || ! $steps =~ ^[1-9][0-9]*$ ]]; then
    printf 'CPU and steps must be integers\n' >&2
    exit 2
fi
if ! python3 -I -B -c 'import os,sys; sys.exit(int(sys.argv[1]) not in os.sched_getaffinity(0))' "$cpu"; then
    printf 'CPU %s is outside the process affinity set\n' "$cpu" >&2
    exit 2
fi

mkdir -p -- "$output_dir"
install -m 0400 -- "$source_archive" "$output_dir/source-archive.tar.gz"
source_tree=$(mktemp -d)
private=$(mktemp -d)
validation_tmp="$output_dir/.receipt-validation.json.tmp"
trap 'rm -rf -- "$source_tree" "$private"; rm -f -- "$validation_tmp"' EXIT
python3 -I -B -c '
import pathlib, sys, tarfile
with tarfile.open(sys.argv[1], "r:gz") as archive:
    for member in archive.getmembers():
        path = pathlib.PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not (member.isdir() or member.isfile()):
            raise SystemExit(f"unsafe or unsupported archive member: {member.name}")
' "$output_dir/source-archive.tar.gz"
tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_tree"
runner_relative=topics/045-performance-portability-vector-width/experiment/run_host.sh
mapfile -t archived_runners < <(rg --files --hidden --no-ignore "$source_tree" | \
    rg "/${runner_relative}$" | LC_ALL=C sort)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 45 runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")
archive_script_dir="$archive_repo_root/topics/045-performance-portability-vector-width/experiment"
if ! cmp -s -- "${BASH_SOURCE[0]}" "$archive_script_dir/run_host.sh"; then
    printf 'executing host runner differs from the archived runner\n' >&2
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
    printf 'cpu=%s\n' "$cpu"
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'allowed_affinity=%s\n' "$(taskset --pid --cpu-list $$)"
    printf 'smt_active=%s\n' "$(tr -d '\n' </sys/devices/system/cpu/smt/active 2>/dev/null || printf unavailable)"
    printf 'thread_siblings=%s\n' "$(tr -d '\n' <"/sys/devices/system/cpu/cpu${cpu}/topology/thread_siblings_list")"
    printf 'perf_event_paranoid=%s\n' "$(tr -d '\n' </proc/sys/kernel/perf_event_paranoid)"
    printf 'cpufreq_available=%s\n' "$([[ -d /sys/devices/system/cpu/cpu${cpu}/cpufreq ]] && printf yes || printf no)"
    printf 'turbostat_available=%s\n' "$(command -v turbostat >/dev/null && printf yes || printf no)"
    printf 'steps=%s\n' "$steps"
    printf 'warmup_steps=%s\n' "$warmup_steps"
    printf 'build_flags=-O3 -std=c11 -Wall -Wextra -Werror -fno-tree-vectorize -ffp-contract=fast -fno-omit-frame-pointer\n'
    uname -a
    lscpu
    gcc --version
    python3 --version
    objdump --version
    nm --version
    rustc -Vv
    cargo -Vv
    perf version
    rustc -C target-cpu=native --print cfg
    rustc --print target-features
    gcc -march=native -Q --help=target
    perf list hw
} >"$output_dir/host.txt" 2>&1

(
    cd -- "$archive_repo_root"
    CARGO_TARGET_DIR="$private/cargo-target" cargo test --locked --offline \
        --package performance-portability-vector-width --lib
    CARGO_TARGET_DIR="$private/cargo-target" cargo test --locked --offline \
        --package performance-portability-vector-width --doc
    printf 'CORRECTNESS_STATUS=pass\n'
) >"$output_dir/correctness.txt" 2>&1

source_file="$archive_script_dir/width_bench.c"
binary="$private/width_bench"
{
    printf 'COMMAND=gcc -O3 -std=c11 -Wall -Wextra -Werror -fno-tree-vectorize -ffp-contract=fast -fno-omit-frame-pointer width_bench.c -lm -o width_bench\n'
    gcc -O3 -std=c11 -Wall -Wextra -Werror -fno-tree-vectorize \
        -ffp-contract=fast -fno-omit-frame-pointer "$source_file" -lm -o "$binary"
    printf 'BUILD_STATUS=pass\n'
} >"$output_dir/build.txt" 2>&1
mkdir -- "$output_dir/binary"
install -m 0500 -- "$binary" "$output_dir/binary/width_bench"
binary="$output_dir/binary/width_bench"
sha256sum -- "$binary" >"$output_dir/binary.sha256"
"$binary" --check >>"$output_dir/correctness.txt" 2>&1
"$binary" --list >"$output_dir/modes.txt"

python3 -I -B "$archive_script_dir/self_test.py" \
    --output "$output_dir/protocol-self-test.json"
"$archive_script_dir/capture_codegen.sh" "$binary" "$output_dir/codegen"
python3 -I -B "$archive_script_dir/run_experiment.py" \
    --binary "$binary" --outdir "$output_dir/experiment" --cpu "$cpu" \
    --steps "$steps" --warmup-steps "$warmup_steps" --blocks 8 --aa-blocks 8 \
    --seed 20260824 --washout-seconds 0.2 >"$output_dir/run-experiment.txt" 2>&1

write_source_manifest "$output_dir/source-manifest-after.sha256"
diff -u "$output_dir/source-manifest-before.sha256" \
    "$output_dir/source-manifest-after.sha256" >"$output_dir/source-manifest.diff"

python3 -I -B "$archive_script_dir/validate_receipts.py" "$output_dir" \
    --expected-label "$SSH_TARGET_LABEL" \
    --expected-resolved-host "$SSH_RESOLVED_HOSTNAME" \
    --expected-source-commit "$SOURCE_COMMIT" \
    --expected-archive-sha256 "$SOURCE_ARCHIVE_SHA256" --output "$validation_tmp"
write_source_manifest "$private/source-manifest-final.sha256"
cmp -s "$output_dir/source-manifest-before.sha256" "$private/source-manifest-final.sha256" || {
    printf 'source changed during receipt validation\n' >&2
    exit 2
}
final_binary_sha256=$(sha256sum -- "$binary" | awk '{print $1}')
initial_binary_sha256=$(awk '{print $1}' "$output_dir/binary.sha256")
if [[ $final_binary_sha256 != "$initial_binary_sha256" ]]; then
    printf 'binary changed during host gates\n' >&2
    exit 2
fi
mv -- "$validation_tmp" "$output_dir/receipt-validation.json"
printf 'status=PASS\n' >"$output_dir/status.txt"
