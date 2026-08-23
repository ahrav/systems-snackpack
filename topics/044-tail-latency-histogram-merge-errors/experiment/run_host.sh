#!/bin/bash -p
set -euo pipefail

# Execute the exact archived Topic 44 source. The experiment reports semantic
# output and generated code, not timing.
if [[ $- != *p* ]]; then
    echo "run this script directly so privileged Bash suppresses BASH_ENV" >&2
    exit 2
fi
if [[ $# -ne 4 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT ARCHIVE_SHA256 SOURCE_ARCHIVE" >&2
    exit 2
fi
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME}"

export LANG=C
export LC_ALL=C
unset BASH_ENV CDPATH GLOBIGNORE PYTHONHOME PYTHONPATH RIPGREP_CONFIG_PATH

output_dir=$(realpath -m -- "$1")
source_commit=${2,,}
expected_archive_digest=${3,,}
source_archive=$(realpath -- "$4")
if [[ $(dirname -- "$output_dir") != /tmp || -e $output_dir ]]; then
    echo "OUTPUT_DIR must be a new direct child of /tmp" >&2
    exit 2
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ || ! $expected_archive_digest =~ ^[0-9a-f]{64}$ ]]; then
    echo "invalid source identity" >&2
    exit 2
fi

mkdir -m 0700 -- "$output_dir" "$output_dir/codegen"
work_dir="$output_dir/.work"
extract_dir="$work_dir/source"
target_dir="$work_dir/target"
mkdir -m 0700 -- "$work_dir" "$extract_dir" "$target_dir"

actual_archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $actual_archive_digest != "$expected_archive_digest" ]]; then
    echo "archive digest mismatch" >&2
    exit 2
fi
printf '%s  source.tar.gz\n' "$actual_archive_digest" >"$output_dir/archive.sha256"
cp -- "$source_archive" "$output_dir/source.tar.gz"
if tar -tzf "$source_archive" | rg '(^/|(^|/)\.\.(/|$))'; then
    echo "archive contains an unsafe path" >&2
    exit 2
fi
tar -xzf "$source_archive" -C "$extract_dir"

runner_relative=topics/044-tail-latency-histogram-merge-errors/experiment/run_host.sh
mapfile -t runner_paths < <(rg --files --hidden --no-ignore "$extract_dir" | rg "/${runner_relative}$")
if [[ ${#runner_paths[@]} -ne 1 ]]; then
    echo "archive must contain one Topic 44 runner" >&2
    exit 2
fi
source_root=${runner_paths[0]%/"$runner_relative"}
source_root=$(realpath -- "$source_root")
topic_dir="$source_root/topics/044-tail-latency-histogram-merge-errors"
if ! cmp -- "${BASH_SOURCE[0]}" "$topic_dir/experiment/run_host.sh"; then
    echo "executed runner differs from archived runner" >&2
    exit 2
fi

embedded_commit=$(git get-tar-commit-id < <(gzip -dc "$source_archive"))
if [[ $embedded_commit != "$source_commit" ]]; then
    echo "archive commit differs from requested commit" >&2
    exit 2
fi

write_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -0 |
            LC_ALL=C sort -z |
            xargs -0 sha256sum --
    ) >"$destination"
}

# Bind each receipt to both its quoted command and a successful exit.
run_record() {
    local destination=$1
    shift
    {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
        printf 'EXIT_STATUS=0\n'
    } >"$output_dir/$destination" 2>&1
}

executing_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $executing_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    echo "executing host $executing_hostname differs from $SSH_RESOLVED_HOSTNAME" >&2
    exit 2
fi
if [[ $SSH_TARGET_LABEL == xxl ]]; then
    [[ $architecture == x86_64 ]] || { echo "xxl is not x86_64" >&2; exit 2; }
else
    [[ $architecture == aarch64 || $architecture == arm64 ]] || {
        echo "fixed Arm target is not Arm" >&2
        exit 2
    }
fi

{
    printf 'target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'executing_hostname=%s\n' "$executing_hostname"
    printf 'architecture=%s\n' "$architecture"
    printf 'available_cpu_count=%s\n' "$(nproc)"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'archive_sha256=%s\n' "$actual_archive_digest"
    printf 'build_flags=%s\n' '-C opt-level=3 -C target-cpu=native -C panic=abort'
} >"$output_dir/host-identity.txt"

write_manifest "$output_dir/source-manifest-before.sha256"
run_record kernel.txt uname -a
run_record cpuinfo.txt lscpu
run_record rustc-version.txt rustc -vV
run_record cargo-version.txt cargo -Vv
run_record gcc-version.txt gcc --version
if command -v clang >/dev/null 2>&1; then
    run_record clang-version.txt clang --version
else
    printf 'clang=unavailable\n' >"$output_dir/clang-version.txt"
fi
run_record rust-target-features.txt rustc --print target-features
run_record native-target-cfg.txt rustc -C target-cpu=native --print cfg

export CARGO_TARGET_DIR="$target_dir"
run_record test.txt cargo test --manifest-path "$source_root/Cargo.toml" --locked --offline \
    --package tail-latency-histogram-merge-errors
run_record build.txt env RUSTFLAGS='-C opt-level=3 -C target-cpu=native -C panic=abort' \
    cargo build --manifest-path "$source_root/Cargo.toml" --locked --offline --release \
    --package tail-latency-histogram-merge-errors --example histogram_merge_probe

binary="$target_dir/release/examples/histogram_merge_probe"
run_record run-processes.txt python3 -I -B "$topic_dir/experiment/run_processes.py" \
    --binary "$binary" --expected "$topic_dir/experiment/expected.txt" \
    --output "$output_dir/processes" --runs 8
cp -- "$binary" "$output_dir/processes/histogram_merge_probe"
cp -- "$topic_dir/experiment/expected.txt" "$output_dir/expected.txt"

run_record codegen/rustc-command.txt rustc --crate-name histogram_merge_errors \
    --edition=2024 --crate-type=lib -C opt-level=3 -C target-cpu=native \
    -C panic=abort --emit=asm,llvm-ir,obj --out-dir "$output_dir/codegen" \
    "$topic_dir/src/lib.rs"
mv "$output_dir/codegen/histogram_merge_errors.s" "$output_dir/codegen/library.asm"
mv "$output_dir/codegen/histogram_merge_errors.ll" "$output_dir/codegen/library.ll"
mv "$output_dir/codegen/histogram_merge_errors.o" "$output_dir/codegen/library.o"
run_record codegen/library.objdump.txt objdump -drwC "$output_dir/codegen/library.o"
run_record codegen/linked.objdump.txt objdump -drwC "$output_dir/processes/histogram_merge_probe"
run_record codegen/linked.symbols.txt nm -n "$output_dir/processes/histogram_merge_probe"
(
    cd "$output_dir"
    sha256sum processes/histogram_merge_probe codegen/library.o
) >"$output_dir/codegen/sha256sums.txt"

write_manifest "$output_dir/source-manifest-after.sha256"
cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"
run_record validation.txt python3 -I -B "$topic_dir/experiment/validate_receipts.py" \
    "$output_dir" --expected-label "$SSH_TARGET_LABEL" \
    --expected-resolved-host "$SSH_RESOLVED_HOSTNAME"
rm -rf -- "$work_dir"
printf 'status=PASS\n' >"$output_dir/status.txt"
