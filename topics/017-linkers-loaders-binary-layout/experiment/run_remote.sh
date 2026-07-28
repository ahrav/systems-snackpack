#!/usr/bin/env bash
set -euo pipefail

# Validates a clean glibc Linux source tree, runs Topic 17, and writes evidence
# outside the repository.

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/017-linkers-loaders-binary-layout"
topic_dir="$repo_root/$topic_rel"

for tool in \
    awk bash cargo cc cmp date getconf git gzip ld ldd lscpu mkdir mktemp mv \
    objdump python3 readelf rg rm rustc sha256sum sort taskset uname xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done

if [[ ! -r "$topic_dir/experiment/binding_experiment.py" ]]; then
    printf 'repository lacks the Topic 17 experiment\n' >&2
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
    allowed="$(rg -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
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
# its own source identity.
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
    source_commit="$SOURCE_COMMIT"
    source_commit_verification=declared-archive
fi
if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
    printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
    exit 2
fi

build_dir="$(mktemp -d)"
experiment_work_dir="$build_dir/experiment-work"
cleanup() {
    rm -rf -- "$build_dir"
}
trap cleanup EXIT
gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
mkdir -p -- "$gates_dir"

# Emits NUL-separated paths relative to the caller's directory. Callers sort;
# `manifest_source` keeps the collation that retained manifests were built under,
# while the checkout gate below sorts in C to match `git ls-files`.
scan_source_paths() {
    rg --files -uu -g '!/.git/' -g '!/target/' -0
}
manifest_source() {
    (
        cd "$repo_root"
        scan_source_paths \
            | sort -z \
            | xargs -0 sha256sum --
    )
}

if [[ "$source_commit_verification" == git-checkout ]]; then
    # `-uu` disables ignore rules and `git status --porcelain` omits ignored
    # files, so a clean checkout can still carry files absent from the commit.
    # Such a file enters the manifest and can influence the gates while the run
    # is attributed to HEAD, and the manifest stops reproducing from
    # `git archive $source_commit`.
    untracked_scanned="$(
        cd "$repo_root"
        LC_ALL=C comm -23 \
            <(scan_source_paths | tr '\0' '\n' | LC_ALL=C sort) \
            <(git ls-files | LC_ALL=C sort)
    )"
    if [[ -n "$untracked_scanned" ]]; then
        printf 'source tree carries files absent from %s:\n%s\n' \
            "$source_commit" "$untracked_scanned" >&2
        exit 2
    fi
fi
manifest_source >"$output_dir/source-files.before.sha256"

# Probe from inside the source tree: rustup applies a directory toolchain
# override only to `rustc` and `cargo` invoked at or below the directory holding
# `rust-toolchain.toml`. Probing from the caller's directory would record an
# ambient toolchain while every cargo gate below runs under the pinned one.
(
    cd "$repo_root"
    printf 'utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-unknown}"
    printf 'selected_cpu=%s\n' "$cpu"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf 'page_size=%s\n' "$(getconf PAGESIZE)"
    printf 'aslr=%s\n' "$(rg -m 1 '^[0-9]+$' /proc/sys/kernel/randomize_va_space)"
    printf '\naffinity\n'
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo
    printf '\ncc\n'
    cc --version
    cc -dumpmachine
    printf '\nrustc\n'
    rustc -vV
    printf '\ncargo\n'
    cargo -vV
    printf '\ntarget_cfg\n'
    rustc --print cfg -C target-cpu=native
    printf '\nlinker\n'
    ld --version
    printf '\nlibc\n'
    ldd --version
    getconf GNU_LIBC_VERSION
    printf '\nelf_tools\n'
    readelf --version
    objdump --version
) >"$output_dir/host.txt" 2>&1

if [[ "$source_commit_verification" == git-checkout ]]; then
    (
        cd "$repo_root"
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
    cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    cargo clippy --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    cargo bench --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1
(
    cd "$repo_root"
    PYTHONPYCACHEPREFIX="$build_dir/pycache" \
        python3 -m py_compile "$topic_rel/experiment/binding_experiment.py"
    bash -n "$topic_rel/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

taskset -c "$cpu" python3 "$topic_dir/experiment/binding_experiment.py" \
    --work-dir "$experiment_work_dir" \
    --output-dir "$experiment_dir" \
    --blocks 12 \
    --iterations 25000000 \
    >"$output_dir/process.log" 2>&1

manifest_source >"$output_dir/source-files.after.sha256"
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
