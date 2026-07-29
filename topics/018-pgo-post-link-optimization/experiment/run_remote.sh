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
    tar taskset uname xargs; do
    if ! command -v "$required" >/dev/null 2>&1; then
        printf 'required executable is unavailable: %s\n' "$required" >&2
        exit 2
    fi
done
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 8))'
# Loader state reaches every timed child through the driver: `LD_PRELOAD` and
# `LD_AUDIT` can interpose the calls being timed, `GLIBC_TUNABLES` can change
# allocator and string-routine behaviour, and `LD_BIND_NOW` moves symbol binding
# into startup, which the parent-process clock includes. Nothing in the retained
# provenance would record it, so the rows would be attributed to the binary and
# host alone. Clearing these could break a toolchain that relies on them, so
# refuse and let the operator present a controlled environment.
for loader_variable in \
    LD_PRELOAD LD_AUDIT LD_LIBRARY_PATH LD_BIND_NOW GLIBC_TUNABLES; do
    if [[ -n "${!loader_variable:-}" ]]; then
        printf 'loader environment must be unset for measurement: %s\n' \
            "$loader_variable" >&2
        exit 2
    fi
done
# The gates exist to validate the repository against its pinned toolchain, so
# they must not honour a compiler, flag set, or wrapper chosen by the caller;
# `env -u RUSTUP_TOOLCHAIN` alone leaves all of those in place. Unlike loader
# state these affect only the gates, never a measured binary, so clearing them
# is safe and keeps the gate logs describing the pin recorded in `host.txt`.
gate_env() {
    env \
        -u RUSTUP_TOOLCHAIN \
        -u RUSTC -u RUSTC_WRAPPER -u RUSTC_WORKSPACE_WRAPPER -u RUSTC_BOOTSTRAP \
        -u RUSTFLAGS -u CARGO_ENCODED_RUSTFLAGS -u RUSTDOCFLAGS \
        -u CARGO_BUILD_RUSTC -u CARGO_BUILD_RUSTC_WRAPPER \
        -u CARGO_BUILD_RUSTC_WORKSPACE_WRAPPER \
        -u CARGO_BUILD_RUSTFLAGS -u CARGO_BUILD_RUSTDOCFLAGS \
        -u CARGO_BUILD_TARGET -u CARGO_BUILD_TARGET_DIR \
        "$@"
}
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
if [[ -d "$output_dir" ]]; then
    # `rg --files` lists regular files and does not follow symlinks, so a
    # pre-existing entry such as `gates -> /elsewhere` read as an empty
    # directory. The gate logs would then be written through it, land outside
    # this tree, and be omitted from `evidence.sha256`, leaving a run that
    # reports success while retaining none of the gate output it authenticates.
    # A glob sees every entry, including symlinks and dot-prefixed names.
    shopt -s dotglob nullglob
    output_dir_entries=("$output_dir"/*)
    shopt -u dotglob nullglob
    if ((${#output_dir_entries[@]} > 0)); then
        printf 'OUTPUT_DIRECTORY must be empty: %s\n' "$output_dir" >&2
        exit 2
    fi
elif [[ -e "$output_dir" ]]; then
    printf 'OUTPUT_DIRECTORY must be a directory: %s\n' "$output_dir" >&2
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

# Compare against the work-tree root rather than testing for repository
# discovery: `rev-parse --git-dir` walks upward, so an archive extracted beneath
# an unrelated checkout would otherwise adopt that ancestor's HEAD and status as
# its own source identity and skip the archive checks below.
if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" == "$repo_root" ]]; then
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
    # The digests above bind the transferred bytes, not the commit id: an
    # extracted archive carries no object store, so nothing on this host can
    # recompute `git archive $SOURCE_COMMIT`. The label names what is verified
    # here — archive and manifest — and `source_commit` remains a caller
    # declaration whose binding to these bytes is established by the sender.
    source_commit_verification=verified-archive-and-manifest
fi
if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
    printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
    exit 2
fi

scratch_dir="$(mktemp -d)"
# `mktemp` places its result under `$TMPDIR`. Inside OUTPUT_DIRECTORY the
# snapshot, the experiment work directory, and the evidence manifest's own
# temporary file become files that `evidence.sha256` hashes, and the temporaries
# are then removed, so verifying it fails. Inside the source tree the scratch
# contents fall within the source walk, so the snapshot copy picks up transient
# files that the origin manifest never listed and the run aborts on itself.
if [[ "$scratch_dir" == "$output_dir" || "$scratch_dir" == "$output_dir"/* ]]; then
    printf 'TMPDIR must resolve outside OUTPUT_DIRECTORY: %s\n' "$scratch_dir" >&2
    exit 2
fi
if [[ "$scratch_dir" == "$input_root" || "$scratch_dir" == "$input_root"/* ]]; then
    printf 'TMPDIR must resolve outside REPOSITORY_ROOT: %s\n' "$scratch_dir" >&2
    exit 2
fi
experiment_work_dir="$scratch_dir/experiment-work"
# Cargo resolves a relative target directory against its working directory,
# which is the snapshot, and the source walk excludes only `target/`. A caller
# with `CARGO_TARGET_DIR=build` would drop gate artifacts into the snapshot and
# fail the post-experiment mutation check after every measurement had been
# taken. Keep gate artifacts out of the snapshot entirely.
export CARGO_TARGET_DIR="$scratch_dir/cargo-target"
cleanup() {
    rm -rf -- "$scratch_dir"
}
trap cleanup EXIT
gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
mkdir -p -- "$gates_dir"

# Emits NUL-separated paths relative to the caller's directory, and is the only
# definition of which files count as source. `!.git` excludes the gitdir pointer
# file a linked worktree carries in place of a directory; its contents name an
# absolute path on the running host, so it is not source.
scan_source_paths() {
    rg --files -uu -g '!.git/' -g '!.git' -g '!target/' -0
}
# `LC_ALL=C` fixes the ordering to bytes. Collation is locale-dependent, so an
# unpinned sort makes this digest depend on the environment of whoever generated
# it: the same extracted tree hashes differently under en_US.UTF-8 than under C,
# which would reject an archive whose bytes are correct.
manifest_source() {
    manifest_root="$1"
    (
        cd "$manifest_root"
        scan_source_paths \
            | LC_ALL=C sort -z \
            | xargs -0 sha256sum --
    )
}

manifest_source "$input_root" >"$output_dir/source-files.origin.sha256"
if [[ "$source_commit_verification" == git-checkout ]]; then
    # Reproduce the manifest from the commit rather than comparing path sets.
    # The scan passes `-uu` while `git status --porcelain` omits ignored files,
    # and neither status nor a one-way path comparison sees a sparse or
    # skip-worktree path missing from the tree, or an assume-unchanged file whose
    # bytes no longer match its blob. Any of those leaves the manifest and the
    # snapshot disagreeing with `source_commit` while the run is attributed to it.
    commit_tree="$scratch_dir/commit-tree"
    mkdir -p -- "$commit_tree"
    git -C "$input_root" archive --format=tar "$source_commit" \
        | tar -xf - -C "$commit_tree"
    manifest_source "$commit_tree" >"$output_dir/source-files.commit.sha256"
    if ! cmp -s \
        "$output_dir/source-files.origin.sha256" \
        "$output_dir/source-files.commit.sha256"; then
        printf 'source tree does not reproduce from %s:\n' "$source_commit" >&2
        LC_ALL=C diff -- \
            "$output_dir/source-files.commit.sha256" \
            "$output_dir/source-files.origin.sha256" >&2 || true
        exit 2
    fi
else
    # Bind the archive to the tree being measured. The digest check above proves
    # only that the named archive matches its declared hash, and the manifest
    # check below proves only that this tree matches its declared hash; both are
    # caller-supplied constants, so a stale archive paired with an unrelated
    # extracted tree satisfies each independently and the retained provenance
    # records an archive digest that cannot reproduce the measured snapshot.
    archive_tree="$scratch_dir/archive-tree"
    mkdir -p -- "$archive_tree"
    tar -xf "$SOURCE_ARCHIVE_PATH" -C "$archive_tree"
    manifest_source "$archive_tree" >"$output_dir/source-files.archive.sha256"
    if ! cmp -s \
        "$output_dir/source-files.origin.sha256" \
        "$output_dir/source-files.archive.sha256"; then
        printf 'source tree does not reproduce from %s:\n' \
            "$SOURCE_ARCHIVE_PATH" >&2
        LC_ALL=C diff -- \
            "$output_dir/source-files.archive.sha256" \
            "$output_dir/source-files.origin.sha256" >&2 || true
        exit 2
    fi
fi
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
    scan_source_paths \
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
    gate_env cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    gate_env cargo test --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    gate_env cargo test --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    gate_env cargo clippy --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    gate_env cargo bench --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    gate_env RUSTDOCFLAGS="-D warnings" \
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

manifest_tmp="$scratch_dir/evidence.sha256"
(
    cd "$output_dir"
    rg --files -uu -0 . | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
