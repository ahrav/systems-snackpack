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
    # Require a program, not merely a name that resolves. An exported shell
    # function — `export -f git` arrives as a `BASH_FUNC_git%%` environment entry
    # — satisfies a bare `command -v` and then answers every unqualified call, so
    # a caller could forge `rev-parse`, `status`, or `archive` output and with it
    # the whole source provenance. Aliases and builtins shadow the same way. Only
    # a program resolves to an absolute path.
    resolved_required="$(command -v "$required" || true)"
    if [[ "$resolved_required" != /* ]]; then
        printf '%s\n' \
            "required executable is not a program: $required -> ${resolved_required:-not found}" \
            "a shell function, alias, or builtin shadowing a tool would forge its output" >&2
        exit 2
    fi
done
python3 -c 'import sys; raise SystemExit(sys.version_info < (3, 8))'
# Loader and libc state reaches every timed child through the driver: `LD_PRELOAD`
# and `LD_AUDIT` can interpose the calls being timed, `LD_DEBUG` adds diagnostic
# work to each startup, and `GLIBC_TUNABLES` and the older `MALLOC_*` knobs change
# allocator behaviour. Nothing in the retained provenance records it, so the rows
# would be attributed to the binary and host alone. Sweep the namespaces rather
# than name members: the loader and libc keep adding variables, and a list is a
# snapshot of the ones known when it was written. Clearing these could break a
# toolchain that relies on them, so refuse and let the operator present a
# controlled environment.
for loader_variable in $(compgen -e); do
    case "$loader_variable" in
        LD_* | GLIBC_* | MALLOC_*)
            printf '%s\n' \
                "loader environment must be unset for measurement: $loader_variable" \
                "every timed probe inherits it and no receipt records it" >&2
            exit 2
            ;;
    esac
done
# The gates exist to validate the repository against its pinned toolchain, so
# they must not honour a compiler, flag set, or wrapper chosen by the caller.
# Naming the variables to remove cannot work: Cargo derives an environment
# variable from every configuration key, so `CARGO_TARGET_<TRIPLE>_RUSTFLAGS`
# and `CARGO_TARGET_<TRIPLE>_LINKER` exist for each target triple and the list
# grows with Cargo. Start from an empty environment and name what the gates may
# see instead. `HOME` stays because rustup resolves `RUSTUP_HOME` beneath it;
# `CARGO_HOME` is redirected because Cargo also merges configuration files that
# no environment change reaches.
gate_env() {
    env -i \
        PATH="$gate_toolchain_bin:$PATH" \
        HOME="$HOME" \
        LC_ALL=C \
        ${RUSTUP_HOME:+RUSTUP_HOME="$RUSTUP_HOME"} \
        CARGO_HOME="$gate_cargo_home" \
        CARGO_TARGET_DIR="$CARGO_TARGET_DIR" \
        "$@"
}
# `git replace` refs and grafts are honoured by object reads, so `git archive`
# can emit a replacement tree while `rev-parse HEAD` still reports the original
# commit. The manifest would then reproduce from a local rewrite that a clone of
# `source_commit` does not contain. Read raw objects for every provenance query.
export GIT_NO_REPLACE_OBJECTS=1
# `TAR_OPTIONS` is applied to every `tar` invocation, so an ambient
# `--exclude` or `--strip-components` would silently filter the reference tree
# this script extracts to verify the measured one against.
unset TAR_OPTIONS
experiment_rustup_toolchain="${EXPERIMENT_RUSTUP_TOOLCHAIN:-stable}"
# Resolve toolchain binaries by path rather than trusting a `PATH` name to be a
# rustup proxy. A standalone binary earlier on `PATH` ignores rustup, and it can
# report the version of the toolchain it shadows, so no version comparison
# separates the two. Prepending the resolved toolchain's own bin directory makes
# `rustc`, `cargo`, and cargo's subcommand helpers resolve from that toolchain
# with no proxy involved. An uninstalled toolchain resolves to nothing, so this
# also reports its absence.
experiment_rustc="$(
    rustup which --toolchain "$experiment_rustup_toolchain" rustc 2>/dev/null || true
)"
if [[ ! -x "$experiment_rustc" ]]; then
    printf 'rustup cannot resolve rustc for toolchain %s\n' \
        "$experiment_rustup_toolchain" >&2
    exit 2
fi
experiment_toolchain_bin="${experiment_rustc%/*}"

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
        rg --no-config -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}' || true
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
# Compare physical paths: `mktemp` echoes the spelling it was given, so a
# `TMPDIR` that is a symlink into one of these trees passes a textual prefix
# test while the scratch tree is physically inside it.
scratch_dir="$(cd -- "$scratch_dir" && pwd -P)"
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
# Cargo merges configuration from `$CARGO_HOME/config.toml` and every `.cargo/`
# directory above its working directory, none of which the process environment
# controls, so a caller-local `[build] rustflags` or linker override still
# reaches the gates. Point them at an empty directory instead. The workspace
# declares no external dependencies, so no registry is needed.
gate_cargo_home="$scratch_dir/cargo-home"
mkdir -p -- "$gate_cargo_home"
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
    rg --no-config --files -uu -g '!.git/' -g '!.git' -g '!target/' -0
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

# The manifest hashes contents, so it cannot see executable-bit drift. In a
# checkout `core.fileMode=false` or a mode-blind filesystem hides that drift from
# `git status`; in an extracted archive a later `chmod` leaves the digests intact;
# and a snapshot copy takes its modes from the caller's umask. The measured tree
# carries executable scripts, so compare bits between trees rather than widening
# the manifest, whose format the retained `SOURCE_MANIFEST_SHA256` values depend
# on. Each caller compares manifests first, so the path sets are already known
# equal.
require_matching_modes() {
    subject_tree="$1"
    reference_tree="$2"
    reference_name="$3"
    mode_drift=""
    while IFS= read -r -d '' scanned_path; do
        if [[ -x "$subject_tree/$scanned_path" ]] \
            && [[ ! -x "$reference_tree/$scanned_path" ]]; then
            mode_drift+="unexpectedly executable: $scanned_path"$'\n'
        elif [[ ! -x "$subject_tree/$scanned_path" ]] \
            && [[ -x "$reference_tree/$scanned_path" ]]; then
            mode_drift+="missing executable bit: $scanned_path"$'\n'
        fi
    done < <(cd "$reference_tree" && scan_source_paths)
    if [[ -n "$mode_drift" ]]; then
        printf 'file modes do not match %s:\n%s' \
            "$reference_name" "$mode_drift" >&2
        exit 2
    fi
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
    # `tar.umask` restricts the permission bits `git archive` emits, so a local
    # setting would strip modes from the reference tree itself.
    git -C "$input_root" -c tar.umask=0 archive --format=tar "$source_commit" \
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
    # Take the commit's modes from the object database rather than from the
    # extracted tree. `tar.umask` and archive attributes both shape what
    # `git archive` emits, so a reference tree can agree with a drifted worktree
    # because the same local configuration reduced both. `ls-tree` reports what
    # the commit records. Regular blobs only: a symlink's `-x` follows its target
    # and a gitlink has no worktree file here.
    mode_drift=""
    while IFS= read -r -d '' tree_entry; do
        tree_mode="${tree_entry%% *}"
        tree_path="${tree_entry#*$'\t'}"
        case "$tree_mode" in
            100755)
                [[ -x "$input_root/$tree_path" ]] \
                    || mode_drift+="missing executable bit: $tree_path"$'\n'
                ;;
            100644)
                [[ ! -x "$input_root/$tree_path" ]] \
                    || mode_drift+="unexpectedly executable: $tree_path"$'\n'
                ;;
        esac
    done < <(git -C "$input_root" ls-tree -r -z "$source_commit")
    if [[ -n "$mode_drift" ]]; then
        printf 'file modes do not match %s:\n%s' "$source_commit" "$mode_drift" >&2
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
    require_matching_modes "$input_root" "$archive_tree" "$SOURCE_ARCHIVE_PATH"
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
        | xargs -0 cp --parents --preserve=mode --target-directory="$snapshot_root" --
)
manifest_source "$snapshot_root" >"$output_dir/source-files.before.sha256"
if ! cmp -s \
    "$output_dir/source-files.origin.sha256" \
    "$output_dir/source-files.before.sha256"; then
    printf 'immutable source snapshot does not match the verified input\n' >&2
    exit 1
fi
require_matching_modes "$snapshot_root" "$input_root" "the verified input"
repo_root="$snapshot_root"
topic_dir="$repo_root/$topic_rel"

# Cargo merges `.cargo/config.toml` from its working directory and every parent,
# which no environment change reaches, so a configuration above the snapshot
# still decides what the gates validate. The snapshot sits under `TMPDIR`, so
# its ancestors are the caller's choice; refuse rather than validate against
# them. Pure parameter expansion so this adds no tool dependency.
config_ancestor="$repo_root"
while :; do
    for cargo_config in \
        "$config_ancestor/.cargo/config.toml" \
        "$config_ancestor/.cargo/config"; do
        if [[ -e "$cargo_config" ]]; then
            printf '%s\n' \
                "Cargo configuration above the snapshot would reach the gates: $cargo_config" \
                "set TMPDIR to a location with no .cargo configuration above it" >&2
            exit 2
        fi
    done
    [[ "$config_ancestor" == "/" ]] && break
    config_ancestor="${config_ancestor%/*}"
    [[ -z "$config_ancestor" ]] && config_ancestor=/
done

# Resolve the gate toolchain from inside the snapshot, so `rust-toolchain.toml`
# selects it exactly as the receipts claim, then use that toolchain's own bin
# directory for the gates instead of whatever `PATH` offers. `RUSTUP_TOOLCHAIN`
# is removed for the query because it outranks the file: with it set the gates
# would validate against the caller's choice while the receipts named the pin.
gate_toolchain="$(
    cd "$repo_root" \
        && env -u RUSTUP_TOOLCHAIN rustup show active-toolchain | awk '{print $1}'
)"
gate_cargo="$(rustup which --toolchain "$gate_toolchain" cargo 2>/dev/null || true)"
if [[ ! -x "$gate_cargo" ]]; then
    printf 'rustup cannot resolve cargo for the repository toolchain %s\n' \
        "$gate_toolchain" >&2
    exit 2
fi
gate_toolchain_bin="${gate_cargo%/*}"

# A checkout run never reads the archive variables, so echoing whatever the
# caller's shell still exports would record an archive path and digest — and an
# expected manifest digest — that nothing verified, beside
# `source_commit_verification=git-checkout`. Report them only for the branch that
# checks them.
if [[ "$source_commit_verification" == verified-archive-and-manifest ]]; then
    recorded_archive_path="$SOURCE_ARCHIVE_PATH"
    recorded_archive_sha256="$SOURCE_ARCHIVE_SHA256"
    recorded_expected_manifest_sha256="$SOURCE_MANIFEST_SHA256"
else
    recorded_archive_path=not-applicable
    recorded_archive_sha256=not-applicable
    recorded_expected_manifest_sha256=not-applicable
fi
{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_path=%s\n' "$recorded_archive_path"
    printf 'source_archive_sha256=%s\n' "$recorded_archive_sha256"
    printf 'source_manifest_sha256=%s\n' "$source_manifest_sha256"
    printf 'immutable_snapshot=%s\n' "$snapshot_root"
    printf 'experiment_rustup_toolchain=%s\n' "$experiment_rustup_toolchain"
    printf 'expected_source_manifest_sha256=%s\n' \
        "$recorded_expected_manifest_sha256"
} >"$output_dir/source-provenance.txt"

{
    cd "$repo_root"
    printf 'utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_sha256=%s\n' "$recorded_archive_sha256"
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
    rg --no-config -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo || true
    # Probe the same resolved binaries the gates and the driver execute. Reading
    # these through `PATH` would let a shadowing compiler describe itself in the
    # receipt while different binaries produced the gate logs and timed rows.
    printf '\nworkspace_rustc\n'
    printf 'resolved=%s\n' "$gate_toolchain_bin/rustc"
    "$gate_toolchain_bin/rustc" -vV
    # Pin the native probes to the measured CPU. `-Ctarget-cpu=native` reports
    # the features of the CPU it runs on, and the driver runs under
    # `taskset -c "$cpu"` while this block inherits the wrapper's affinity, so on
    # a feature-asymmetric host an unpinned probe would describe a different CPU
    # than the one that built and timed the binaries.
    printf '\nworkspace_native_target_cfg (taskset -c %s)\n' "$cpu"
    taskset -c "$cpu" "$gate_toolchain_bin/rustc" --print cfg -Ctarget-cpu=native
    printf '\nexperiment_rustc\n'
    printf 'resolved=%s\n' "$experiment_rustc"
    "$experiment_rustc" -vV
    printf '\nexperiment_native_target_cfg (taskset -c %s)\n' "$cpu"
    taskset -c "$cpu" "$experiment_rustc" --print cfg -Ctarget-cpu=native
    printf '\nexperiment_llvm_profdata_candidates\n'
    host="$("$experiment_rustc" -vV | sed -n 's/^host: //p')"
    sysroot="$("$experiment_rustc" --print sysroot)"
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
        "source_archive_sha256=$recorded_archive_sha256" \
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
    # `-I` isolates the interpreter, which matters more than it looks: `-m` puts
    # the working directory on `sys.path`, and that directory is the snapshot of
    # the source under test, so a `py_compile.py` beside it — or on a caller's
    # `PYTHONPATH` — would replace the module that validates it and the gate would
    # report success without compiling anything. Compiling in-process instead of
    # through `py_compile` writes no bytecode, so the gate cannot mutate the
    # snapshot it is checking; `-I` also ignores `PYTHONPYCACHEPREFIX`, which is
    # what a `py_compile` run would need to keep its output out of the tree.
    python3 -I -c 'import sys
source = open(sys.argv[1], "rb").read()
compile(source, sys.argv[1], "exec")
print("parsed:", sys.argv[1])' "$topic_rel/experiment/pgo_experiment.py"
    bash -n "$topic_rel/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

# Name the driver's environment for the same reason the gates' is named. The
# probe builds link through `cc`, which reads `LIBRARY_PATH`, `COMPILER_PATH`,
# and `GCC_EXEC_PREFIX` — a wrong `GCC_EXEC_PREFIX` fails the link outright and a
# wrong `LIBRARY_PATH` silently changes library resolution — and Python prefixes
# `PYTHONPATH` to `sys.path`, where a local `random.py` or `statistics.py` would
# replace the modules that schedule the probes and summarise the ratios. Neither
# appears in any receipt. `-I` additionally drops user site-packages, which
# survive an allowlist because `HOME` must stay for toolchain resolution.
# `RUSTUP_TOOLCHAIN` still names the toolchain for the receipts and the recorded
# transcript, while the leading `PATH` entry decides which compiler actually runs.
env -i \
    PATH="$experiment_toolchain_bin:$PATH" \
    HOME="$HOME" \
    LC_ALL=C \
    ${RUSTUP_HOME:+RUSTUP_HOME="$RUSTUP_HOME"} \
    RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
    taskset -c "$cpu" python3 -I "$topic_dir/experiment/pgo_experiment.py" \
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
    rg --no-config --files -uu -0 . | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
