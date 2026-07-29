#!/usr/bin/env bash
set -euo pipefail

# Validates an exact Linux source tree, runs Topic 18, and writes evidence
# outside the repository.

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
input_root="$repo_root"
output_dir="$2"
topic_rel="topics/018-pgo-post-link-optimization"
topic_dir="$repo_root/$topic_rel"

for required in \
    awk bash cargo cc clippy-driver cmp cp date env getconf git ld lscpu mkdir \
    mktemp mv nm objdump python3 rg rm rustc rustfmt rustup sed sha256sum sort \
    taskset uname xargs; do
    if ! command -v "$required" >/dev/null 2>&1; then
        printf 'required executable is unavailable: %s\n' "$required" >&2
        exit 2
    fi
done
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 8))'
experiment_rustup_toolchain="${EXPERIMENT_RUSTUP_TOOLCHAIN:-stable}"
if ! RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" rustc -vV >/dev/null 2>&1; then
    printf 'experiment Rust toolchain is unavailable: %s\n' \
        "$experiment_rustup_toolchain" >&2
    exit 2
fi

if [[ ! -r "$topic_dir/experiment/pgo_experiment.py" ]]; then
    printf 'repository lacks the Topic 18 experiment\n' >&2
    exit 2
fi
if [[ -e "$output_dir" ]] && [[ -n "$(rg --files -uu "$output_dir" 2>/dev/null || true)" ]]; then
    printf 'OUTPUT_DIRECTORY must be empty: %s\n' "$output_dir" >&2
    exit 2
fi
mkdir -p -- "$output_dir"
output_dir="$(cd -- "$output_dir" && pwd -P)"
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi

if (($# == 3)); then
    cpu="$3"
else
    allowed="$(
        rg -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}' || true
    )"
    first="${allowed%%,*}"
    cpu="${first%%-*}"
fi
if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]] || ! taskset -c "$cpu" true >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
    exit 2
fi

if git -C "$repo_root" rev-parse --git-dir >/dev/null 2>&1; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
        printf 'repository must be clean\n' >&2
        exit 2
    fi
    source_commit_verification=git-checkout
else
    if ! [[ "${SOURCE_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]]; then
        printf 'SOURCE_COMMIT is required for an archive source tree\n' >&2
        exit 2
    fi
    if ! [[ "${SOURCE_ARCHIVE_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then
        printf 'SOURCE_ARCHIVE_SHA256 is required for an archive source tree\n' >&2
        exit 2
    fi
    if ! [[ "${SOURCE_MANIFEST_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then
        printf 'SOURCE_MANIFEST_SHA256 is required for an archive source tree\n' >&2
        exit 2
    fi
    if [[ ! -f "${SOURCE_ARCHIVE_PATH:-}" ]]; then
        printf 'SOURCE_ARCHIVE_PATH must name the transferred archive\n' >&2
        exit 2
    fi
    actual_archive_sha256="$(sha256sum -- "$SOURCE_ARCHIVE_PATH" | awk '{print $1}')"
    if [[ "$actual_archive_sha256" != "$SOURCE_ARCHIVE_SHA256" ]]; then
        printf 'transferred archive digest does not match SOURCE_ARCHIVE_SHA256\n' >&2
        exit 2
    fi
    source_commit="$SOURCE_COMMIT"
    source_commit_verification=verified-archive-and-manifest
fi
if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
    printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
    exit 2
fi

scratch_dir="$(mktemp -d)"
experiment_work_dir="$scratch_dir/experiment-work"
cleanup() {
    rm -rf -- "$scratch_dir"
}
trap cleanup EXIT
gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
mkdir -p -- "$gates_dir"

manifest_source() {
    manifest_root="$1"
    (
        cd "$manifest_root"
        rg --files -uu -g '!.git/' -g '!target/' -0 \
            | sort -z \
            | xargs -0 sha256sum --
    )
}
manifest_source "$input_root" >"$output_dir/source-files.origin.sha256"
source_manifest_sha256="$(
    sha256sum -- "$output_dir/source-files.origin.sha256" | awk '{print $1}'
)"
if [[ "$source_commit_verification" == verified-archive-and-manifest ]] \
    && [[ "$source_manifest_sha256" != "$SOURCE_MANIFEST_SHA256" ]]; then
    printf 'extracted tree manifest does not match SOURCE_MANIFEST_SHA256\n' >&2
    exit 2
fi

snapshot_root="$scratch_dir/source"
mkdir -p -- "$snapshot_root"
(
    cd "$input_root"
    rg --files -uu -g '!.git/' -g '!target/' -0 \
        | sort -z \
        | xargs -0 cp --parents --target-directory="$snapshot_root" --
)
manifest_source "$snapshot_root" >"$output_dir/source-files.before.sha256"
if ! cmp -s \
    "$output_dir/source-files.origin.sha256" \
    "$output_dir/source-files.before.sha256"; then
    printf 'immutable source snapshot does not match the verified input\n' >&2
    exit 1
fi
repo_root="$snapshot_root"
topic_dir="$repo_root/$topic_rel"

{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_path=%s\n' "${SOURCE_ARCHIVE_PATH:-not-applicable}"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-not-applicable}"
    printf 'source_manifest_sha256=%s\n' "$source_manifest_sha256"
    printf 'immutable_snapshot=%s\n' "$snapshot_root"
    printf 'experiment_rustup_toolchain=%s\n' "$experiment_rustup_toolchain"
    printf 'expected_source_manifest_sha256=%s\n' \
        "${SOURCE_MANIFEST_SHA256:-not-applicable}"
} >"$output_dir/source-provenance.txt"

{
    cd "$repo_root"
    printf 'utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-unknown}"
    printf 'source_manifest_sha256=%s\n' "$source_manifest_sha256"
    printf 'selected_cpu=%s\n' "$cpu"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf '\naffinity\n'
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo || true
    printf '\nworkspace_rustc\n'
    env -u RUSTUP_TOOLCHAIN rustc -vV
    printf '\nworkspace_native_target_cfg\n'
    env -u RUSTUP_TOOLCHAIN rustc --print cfg -Ctarget-cpu=native
    printf '\nexperiment_rustc\n'
    RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" rustc -vV
    printf '\nexperiment_native_target_cfg\n'
    RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
        rustc --print cfg -Ctarget-cpu=native
    printf '\nexperiment_llvm_profdata_candidates\n'
    host="$(
        RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
            rustc -vV | sed -n 's/^host: //p'
    )"
    sysroot="$(
        RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
            rustc --print sysroot
    )"
    printf 'rust_bundled=%s\n' "$sysroot/lib/rustlib/$host/bin/llvm-profdata"
    command -v llvm-profdata || true
    printf '\nlinker_driver\n'
    command -v cc
    cc --version
    cc -dumpmachine
    printf '\nlinker\n'
    command -v ld
    ld --version
    printf '\npost_link_tools\n'
    for post_link_tool in llvm-bolt perf2bolt merge-fdata perf; do
        command -v "$post_link_tool" || true
    done
    printf '\nelf_tools\n'
    nm --version
    objdump --version
    printf '\npython\n'
    python3 --version
} >"$output_dir/host.txt" 2>&1

if [[ "$source_commit_verification" == git-checkout ]]; then
    (
        cd "$input_root"
        git diff --check
    ) >"$gates_dir/git-diff-check.log" 2>&1
else
    printf '%s\n' \
        "status=not-applicable" \
        "reason=Git archives have no index or parent tree." \
        "source_commit=$source_commit" \
        "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
        >"$gates_dir/git-diff-check.log"
fi
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN cargo test --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN cargo test --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN cargo clippy --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN cargo bench --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    env -u RUSTUP_TOOLCHAIN RUSTDOCFLAGS="-D warnings" \
        cargo doc --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1
(
    cd "$repo_root"
    PYTHONPYCACHEPREFIX="$scratch_dir/pycache" \
        python3 -m py_compile "$topic_rel/experiment/pgo_experiment.py"
    bash -n "$topic_rel/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
    taskset -c "$cpu" python3 "$topic_dir/experiment/pgo_experiment.py" \
    --work-dir "$experiment_work_dir" \
    --output-dir "$experiment_dir" \
    --blocks 12 \
    --iterations 20000000 \
    --training-iterations 5000000 \
    >"$output_dir/process.log" 2>&1

manifest_source "$repo_root" >"$output_dir/source-files.after.sha256"
if ! cmp -s \
    "$output_dir/source-files.before.sha256" \
    "$output_dir/source-files.after.sha256"; then
    printf 'source files changed during evidence collection\n' >&2
    exit 1
fi

manifest_tmp="$(mktemp)"
(
    cd "$output_dir"
    rg --files -uu -0 . | sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
