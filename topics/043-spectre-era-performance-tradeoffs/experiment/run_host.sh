#!/usr/bin/env bash
set -euo pipefail

# Bytecode caches would land inside the executing tree and make the pre- and
# post-run source manifests disagree; suppress them for every python child.
export PYTHONDONTWRITEBYTECODE=1

if [[ $# -lt 1 || $# -gt 3 ]]; then
    printf 'usage: %s OUTPUT_DIR [CPU] [ITERATIONS]\n' "$0" >&2
    exit 2
fi
if [[ $(uname -s) != Linux ]]; then
    printf 'Topic 43 host receipts require Linux\n' >&2
    exit 2
fi
: "${SOURCE_COMMIT:?set SOURCE_COMMIT to the exact 40-hex source commit}"
: "${SOURCE_ARCHIVE_SHA256:?set SOURCE_ARCHIVE_SHA256 to the exact source archive digest}"
: "${SOURCE_ARCHIVE_PATH:?set SOURCE_ARCHIVE_PATH to the uploaded Git archive}"
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to xxl or the authorized Arm hostname}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the runtime-resolved hostname}"
SOURCE_COMMIT=${SOURCE_COMMIT,,}
SOURCE_ARCHIVE_SHA256=${SOURCE_ARCHIVE_SHA256,,}
if [[ ! $SOURCE_COMMIT =~ ^[0-9a-f]{40}$ || ! $SOURCE_ARCHIVE_SHA256 =~ ^[0-9a-f]{64}$ ]]; then
    printf 'source commit or archive digest has the wrong shape\n' >&2
    exit 2
fi
source_archive=$(realpath -- "$SOURCE_ARCHIVE_PATH")
if [[ ! -f $source_archive ]]; then
    printf 'source archive is not a regular file: %s\n' "$source_archive" >&2
    exit 2
fi
source_archive_actual=$(sha256sum -- "$source_archive" | awk '{print $1}')
if [[ $source_archive_actual != "$SOURCE_ARCHIVE_SHA256" ]]; then
    printf 'source archive digest mismatch: expected %s, got %s\n' \
        "$SOURCE_ARCHIVE_SHA256" "$source_archive_actual" >&2
    exit 2
fi
pax_header=$(gzip -dc -- "$source_archive" 2>/dev/null | \
    dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_header =~ comment=([0-9a-f]{40}) || ${BASH_REMATCH[1]} != "$SOURCE_COMMIT" ]]; then
    printf 'source archive does not embed commit %s\n' "$SOURCE_COMMIT" >&2
    exit 2
fi

script_dir=$(cd -- "$(dirname -- "$0")" && pwd -P)
topic_dir=$(cd -- "$script_dir/.." && pwd -P)
repo_root=$(cd -- "$topic_dir/../.." && pwd -P)
output_dir=$(realpath -m -- "$1")
cpu=${2:-$(python3 -c 'import os; print(min(os.sched_getaffinity(0)))')}
iterations=${3:-20000000}
runtime_hostname=$(hostname -f)
architecture=$(uname -m)

if [[ $runtime_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    printf 'runtime hostname %s differs from resolved target %s\n' \
        "$runtime_hostname" "$SSH_RESOLVED_HOSTNAME" >&2
    exit 2
fi
case $SSH_TARGET_LABEL in
    xxl)
        [[ $architecture == x86_64 ]] || {
            printf 'xxl resolved to non-x86-64 architecture %s\n' "$architecture" >&2
            exit 2
        }
        ;;
    dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
        [[ $architecture == aarch64 || $architecture == arm64 ]] || {
            printf 'authorized Arm target reported architecture %s\n' "$architecture" >&2
            exit 2
        }
        ;;
    *)
        printf 'unauthorized Topic 43 target label: %s\n' "$SSH_TARGET_LABEL" >&2
        exit 2
        ;;
esac

if [[ -e $output_dir ]]; then
    printf 'output path already exists: %s\n' "$output_dir" >&2
    exit 2
fi
case $output_dir in
    "$repo_root" | "$repo_root"/*)
        printf 'write host receipts outside the repository: %s\n' "$output_dir" >&2
        exit 2
        ;;
esac
if [[ ! $cpu =~ ^[0-9]+$ || ! $iterations =~ ^[1-9][0-9]*$ ]]; then
    printf 'CPU and iterations must be nonnegative and positive integers\n' >&2
    exit 2
fi
if ! python3 -c 'import os,sys; sys.exit(int(sys.argv[1]) not in os.sched_getaffinity(0))' "$cpu"; then
    printf 'CPU %s is outside this process affinity set\n' "$cpu" >&2
    exit 2
fi

mkdir -p -- "$output_dir"
cp -- "$source_archive" "$output_dir/source-archive.tar.gz"
chmod 0400 "$output_dir/source-archive.tar.gz"

source_check=$(mktemp -d)
run_private=$(mktemp -d)
trap 'rm -rf -- "$source_check" "$run_private"' EXIT
tar -xzf "$output_dir/source-archive.tar.gz" -C "$source_check"
runner_relative=topics/043-spectre-era-performance-tradeoffs/experiment/run_host.sh
mapfile -t archived_runners < <(rg --files --hidden --no-ignore "$source_check" | \
    rg "/${runner_relative}$" | LC_ALL=C sort)
if [[ ${#archived_runners[@]} -ne 1 ]]; then
    printf 'source archive must contain exactly one Topic 43 host runner\n' >&2
    exit 2
fi
archive_repo_root=${archived_runners[0]%/"$runner_relative"}
archive_repo_root=$(realpath -- "$archive_repo_root")

write_source_manifest() {
    local root=$1
    local destination=$2
    (
        cd -- "$root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum --
    ) >"$destination"
}

write_source_manifest "$repo_root" "$output_dir/source-manifest-executing.sha256"
write_source_manifest "$archive_repo_root" "$output_dir/source-manifest-archive.sha256"
if ! diff -u "$output_dir/source-manifest-archive.sha256" \
    "$output_dir/source-manifest-executing.sha256" >"$output_dir/source-manifest.diff"; then
    printf 'executing source differs from the supplied Git archive\n' >&2
    exit 2
fi
{
    printf 'captured_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    printf 'source_commit=%s\n' "$SOURCE_COMMIT"
    printf 'source_archive_sha256=%s\n' "$SOURCE_ARCHIVE_SHA256"
    printf 'source_archive_verified_sha256=%s\n' "$source_archive_actual"
    printf 'source_manifest_match=pass\n'
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'runtime_hostname=%s\n' "$runtime_hostname"
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel_release=%s\n' "$(uname -r)"
    printf 'cpu=%s\n' "$cpu"
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'affinity=%s\n' "$(taskset --pid --cpu-list $$)"
    printf 'build_flags=-C target-cpu=native\n'
    uname -a
    lscpu
    rustc -Vv
    cargo -V
    rustc -C target-cpu=native --print cfg
    cc --version | sed -n '1,3p'
    for vulnerability in spectre_v1 spectre_v2 spec_store_bypass retbleed spec_rstack_overflow; do
        path="/sys/devices/system/cpu/vulnerabilities/$vulnerability"
        if [[ -r $path ]]; then
            printf '%s=' "$vulnerability"
            tr '\n' ' ' <"$path"
            printf '\n'
        fi
    done
} >"$output_dir/host.txt"

(
    cd -- "$repo_root"
    cargo test --locked --package spectre-era-performance-tradeoffs --lib --bins
    cargo test --locked --package spectre-era-performance-tradeoffs --doc
) >"$output_dir/correctness.txt" 2>&1

(
    cd -- "$repo_root"
    RUSTFLAGS='-C target-cpu=native' cargo build --locked --release \
        --package spectre-era-performance-tradeoffs --bin spectre-tradeoff-probe
) >"$output_dir/build.txt" 2>&1
# The workspace target directory is mutable: any concurrent cargo invocation
# can replace the probe between codegen capture and the timing schedule.
# Measure a read-only run-private copy and hold its digest for a post-schedule
# recheck so every process is bound to the same bytes.
install -m 0500 -- "$repo_root/target/release/spectre-tradeoff-probe" \
    "$run_private/spectre-tradeoff-probe"
binary="$run_private/spectre-tradeoff-probe"
probe_sha256=$(sha256sum -- "$binary" | awk '{print $1}')
printf 'probe_sha256=%s\n' "$probe_sha256" >"$output_dir/probe.sha256"

python3 "$script_dir/self_test.py" --binary "$binary" --cpu "$cpu" \
    --output "$output_dir/self-test.json"
"$script_dir/capture_codegen.sh" "$binary" "$output_dir/codegen"
python3 "$script_dir/run_aa_screen.py" --binary "$binary" --cpu "$cpu" \
    --iterations "$iterations" --output "$output_dir/aa-processes.jsonl" \
    --summary "$output_dir/aa-summary.json"
python3 "$script_dir/run_processes.py" --binary "$binary" --cpu "$cpu" \
    --iterations "$iterations" --output "$output_dir/timing-processes.jsonl" \
    --summary "$output_dir/timing-summary.json"
probe_sha256_final=$(sha256sum -- "$binary" | awk '{print $1}')
if [[ $probe_sha256_final != "$probe_sha256" ]]; then
    printf 'probe binary changed during the measurement schedule\n' >&2
    exit 2
fi
python3 "$script_dir/validate_receipts.py" "$output_dir"

# The pre-run manifest comparison only proves the tree matched the archive
# before measurement began. Re-derive it after every experiment and validation
# step so receipts cannot silently bind to source modified mid-run.
write_source_manifest "$repo_root" "$output_dir/source-manifest-post-run.sha256"
if ! diff -u "$output_dir/source-manifest-archive.sha256" \
    "$output_dir/source-manifest-post-run.sha256" \
    >"$output_dir/source-manifest-post-run.diff"; then
    printf 'executing source changed during the run\n' >&2
    exit 2
fi
