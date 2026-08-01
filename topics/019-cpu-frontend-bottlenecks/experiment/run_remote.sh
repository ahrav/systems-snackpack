#!/usr/bin/env bash
set -euo pipefail

# Validate an exact Linux source tree and write Topic 19 evidence outside it.

# Bash imports exported functions from the environment before this script runs,
# and a function takes precedence over both PATH lookup and builtins, so an
# imported definition could redirect a tool or make the environment sweep below
# enumerate nothing while still reporting success. Reject any such definition
# before anything else, including before the alias cleanup: a backslash suppresses
# alias expansion but not function lookup, so calling shopt or unalias first would
# hand control to an imported function that could install an alias and self-unset.
# `declare` is dropped first only so that it can be trusted to report the rest,
# and the backslash forms defeat aliases on these two names. A shadowed `unset` is
# outside what this check can establish.
\unset -f declare 2>/dev/null || true
imported_functions="$(\declare -F)"
if [[ -n "$imported_functions" ]]; then
    printf 'refusing to run with shell functions imported from the environment:\n' >&2
    printf '%s\n' "$imported_functions" >&2
    exit 2
fi

# No imported functions remain, so these builtins cannot be shadowed. Bash sources
# BASH_ENV before this script starts, so any aliases and shell options it installed
# are already in effect and cannot be undone by unsetting the variable later.
builtin shopt -u expand_aliases 2>/dev/null || true
builtin unalias -a 2>/dev/null || true
if [[ -n "${BASH_ENV:-}" ]]; then
    printf 'refusing to run with BASH_ENV set: %s\n' "$BASH_ENV" >&2
    printf 'it already ran arbitrary shell code before this script started\n' >&2
    exit 2
fi
# ripgrep reads RIPGREP_CONFIG_PATH unless --no-config is passed, and a config as
# small as --fixed-strings would make every pattern below literal, silently
# emptying the sweep. Clear it before the first rg call; --no-config is also passed
# at each call site.
unset RIPGREP_CONFIG_PATH

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/019-cpu-frontend-bottlenecks"
topic_dir="$repo_root/$topic_rel"

# Cargo, rustup, GCC, Python, and Git honor environment overrides that change
# what the builds and gates below actually run: they select the toolchain,
# replace rustc/rustfmt, inject compiler flags, add implicit header or library
# search paths, redirect compiler subprograms or Python imports, or relocate the
# Git repository and index. Sweeping records each name in swept_environment, so a
# gate can no longer pass under a caller-supplied tool, flag, header, or
# repository while the evidence calls the environment swept. This runs before the
# first Git probe, because GIT_DIR and GIT_WORK_TREE override even git -C.
sweep_pattern='^(CARGO_|GIT_'
sweep_pattern+='|RUSTC$|RUSTC_WRAPPER$|RUSTC_WORKSPACE_WRAPPER$|RUSTC_BOOTSTRAP$'
sweep_pattern+='|RUSTDOC$|RUSTDOCFLAGS$|RUSTFLAGS$|RUSTFMT$'
sweep_pattern+='|RUSTUP_TOOLCHAIN$|CLIPPY_CONF_DIR$|RIPGREP_CONFIG_PATH$'
sweep_pattern+='|CPATH$|C_INCLUDE_PATH$|CPLUS_INCLUDE_PATH$|OBJC_INCLUDE_PATH$'
sweep_pattern+='|COMPILER_PATH$|GCC_EXEC_PREFIX$|GCC_COMPARE_DEBUG$'
sweep_pattern+='|LIBRARY_PATH$|DEPENDENCIES_OUTPUT$|SUNPRO_DEPENDENCIES$'
sweep_pattern+='|PYTHONPATH$|PYTHONHOME$|PYTHONSTARTUP$'
sweep_pattern+='|LD_)'
swept_variables=()
while IFS= read -r variable; do
    swept_variables+=("$variable")
    unset "$variable"
done < <(
    compgen -e \
        | rg --no-config "$sweep_pattern" \
        || true
)

for tool in \
    awk bash cargo cmp date gcc getconf git gzip ln lscpu mkdir mktemp mv nm \
    objdump perf python3 readelf rg rm rustc sha256sum size sort stat taskset \
    uname xargs; do
    # A function shadows PATH lookup while still satisfying command -v, so the
    # gates could run caller-supplied tools. Imported functions were already
    # rejected above; this also refuses any name that does not resolve to a file.
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
    if [[ "$(type -t "$tool" 2>/dev/null || true)" != file ]]; then
        printf 'required tool does not resolve to an executable: %s\n' "$tool" >&2
        exit 2
    fi
done
# command -v proves only that the name resolves to some executable, so record the
# resolved path and content hash of each one. A PATH shim can then be identified
# in the retained evidence instead of being invisible.
resolved_tools=()
for tool in \
    awk bash cargo cmp date gcc getconf git gzip ln lscpu mkdir mktemp mv nm \
    objdump perf python3 readelf rg rm rustc sha256sum size sort stat taskset \
    uname xargs; do
    tool_path="$(command -v "$tool")"
    resolved_tools+=("$(printf '%s %s' "$tool" "$(sha256sum -- "$tool_path")")")
done
if [[ ! -r "$topic_dir/experiment/generate.py" ]] \
    || [[ ! -r "$topic_dir/experiment/frontend_experiment.py" ]]; then
    printf 'repository lacks the Topic 19 experiment\n' >&2
    exit 2
fi

if [[ -L "$output_dir" ]]; then
    printf 'OUTPUT_DIRECTORY must not be a symbolic link: %s\n' "$output_dir" >&2
    exit 2
fi
if [[ -e "$output_dir" ]]; then
    if [[ ! -d "$output_dir" ]]; then
        printf 'OUTPUT_DIRECTORY exists and is not a directory: %s\n' "$output_dir" >&2
        exit 2
    fi
    shopt -s nullglob dotglob
    existing_entries=("$output_dir"/*)
    shopt -u nullglob dotglob
    if ((${#existing_entries[@]} > 0)); then
        printf 'OUTPUT_DIRECTORY must be empty: %s\n' "$output_dir" >&2
        exit 2
    fi
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
    allowed="$(rg --no-config -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
    first="${allowed%%,*}"
    cpu="${first%%-*}"
fi
if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]] \
    || ! taskset -c "$cpu" true >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
    exit 2
fi

if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" == "$repo_root" ]]; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    # --untracked-files=all so that a repository-level status.showUntrackedFiles
    # setting cannot suppress the report.
    if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]]; then
        printf 'repository must be clean\n' >&2
        exit 2
    fi
    if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
        printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
        exit 2
    fi
    unmanifestable="$(
        git -C "$repo_root" ls-files -s | rg --no-config -m 1 -v '^(100644|100755) ' || true
    )"
    if [[ -n "$unmanifestable" ]]; then
        printf 'tracked symbolic links or submodules are unsupported: %s\n' \
            "$unmanifestable" >&2
        exit 2
    fi
    # assume-unchanged (lowercase) and skip-worktree (S) entries keep edits out
    # of git status, so the clean-tree gate above would pass while the manifest
    # hashes working-tree bytes that differ from source_commit.
    hidden_index_flags="$(
        git -C "$repo_root" ls-files -v | rg --no-config -m 1 '^([a-z]|S) ' || true
    )"
    if [[ -n "$hidden_index_flags" ]]; then
        printf 'assume-unchanged or skip-worktree hides edits from the clean-tree gate: %s\n' \
            "$hidden_index_flags" >&2
        exit 2
    fi
    # git status cannot report ignored paths at all, so an ignored Cargo.toml or
    # build.rs under the workspace member glob stays out of the manifest while the
    # --workspace gates still load it -- and Cargo compiles and runs a package-root
    # build.rs automatically. Compare both against the index.
    members_root="${topic_rel%%/*}"
    hidden_members=""
    for candidate in "$repo_root/$members_root"/*/Cargo.toml \
        "$repo_root/$members_root"/*/build.rs; do
        [[ -e "$candidate" ]] || continue
        candidate_rel="${candidate#"$repo_root"/}"
        if ! git -C "$repo_root" ls-files --error-unmatch -- "$candidate_rel" \
            >/dev/null 2>&1; then
            hidden_members+=" $candidate_rel"
        fi
    done
    if [[ -n "$hidden_members" ]]; then
        printf 'untracked workspace files would be loaded by the Cargo gates:%s\n' \
            "$hidden_members" >&2
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

# Cargo, rustfmt, and Clippy all discover configuration from the gate working
# directory upward or from the package root, so an isolated CARGO_HOME is not
# sufficient: a config in repo_root or any ancestor can inject build.rustflags,
# wrappers, linker or target settings, formatting rules, or lint thresholds that
# build-flags.txt never records. A config tracked inside repo_root is part of the
# recorded source and is allowed; anything else is refused.
unrecorded_configs=()
probe_dir="$repo_root"
while :; do
    for candidate in \
        "$probe_dir/.cargo/config.toml" "$probe_dir/.cargo/config" \
        "$probe_dir/rustfmt.toml" "$probe_dir/.rustfmt.toml" \
        "$probe_dir/clippy.toml" "$probe_dir/.clippy.toml"; do
        [[ -e "$candidate" ]] || continue
        if [[ "$probe_dir" == "$repo_root" ]] \
            && git -C "$repo_root" ls-files --error-unmatch -- \
                "${candidate#"$repo_root"/}" >/dev/null 2>&1; then
            continue
        fi
        unrecorded_configs+=("$candidate")
    done
    [[ "$probe_dir" == / ]] && break
    probe_dir="$(dirname -- "$probe_dir")"
done
if ((${#unrecorded_configs[@]} > 0)); then
    printf 'unrecorded tool configuration would apply to the gates:\n' >&2
    printf '  %s\n' "${unrecorded_configs[@]}" >&2
    exit 2
fi

# A rustup directory override outranks rust-toolchain.toml and is stored in
# rustup's own settings rather than the environment, so clearing RUSTUP_TOOLCHAIN
# does not remove it.
if rustup override list >/dev/null 2>&1; then
    rustup_overrides="$(
        rustup override list 2>/dev/null \
            | rg --no-config -v '^no overrides$' || true
    )"
    probe_dir="$repo_root"
    while :; do
        if [[ -n "$rustup_overrides" ]] \
            && printf '%s\n' "$rustup_overrides" \
                | rg --no-config -q -F "$probe_dir"$'\t'; then
            printf 'a rustup directory override outranks rust-toolchain.toml: %s\n' \
                "$probe_dir" >&2
            exit 2
        fi
        [[ "$probe_dir" == / ]] && break
        probe_dir="$(dirname -- "$probe_dir")"
    done
fi

build_dir="$(mktemp -d)"
build_dir="$(cd -- "$build_dir" && pwd -P)"
# A temporary tree inside the evidence directory (TMPDIR=OUTPUT_DIRECTORY) would
# be hashed by the final evidence scan and then deleted by cleanup, leaving
# evidence.sha256 describing files the archive does not contain. A temporary tree
# inside the repository is equally unusable: the root workspace globs topics/*,
# so scratch there becomes a workspace member and the Cargo gates fail to load.
if [[ "$build_dir" == "$output_dir" \
    || "$build_dir" == "$output_dir"/* \
    || "$output_dir" == "$build_dir"/* \
    || "$build_dir" == "$repo_root" \
    || "$build_dir" == "$repo_root"/* \
    || "$repo_root" == "$build_dir"/* ]]; then
    printf 'refusing to place the build tree inside the evidence or source tree\n' >&2
    printf 'build_dir=%s\noutput_dir=%s\nrepo_root=%s\n' \
        "$build_dir" "$output_dir" "$repo_root" >&2
    printf 'set TMPDIR outside OUTPUT_DIRECTORY and the repository\n' >&2
    # The cleanup trap is not installed yet, and mktemp already created this
    # directory. Leaving it inside the workspace glob would break later Cargo
    # invocations until someone removed it by hand.
    rm -rf -- "$build_dir"
    exit 1
fi
manifest_tmp=
cleanup() {
    rm -rf -- "$build_dir"
    if [[ -n "$manifest_tmp" ]]; then
        rm -f -- "$manifest_tmp"
    fi
}
trap cleanup EXIT
gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
frontend_dir="$build_dir/frontend"
mkdir -p -- "$gates_dir" "$frontend_dir"

export CARGO_HOME="$build_dir/cargo-home"
export CARGO_TARGET_DIR="$build_dir/cargo-target"
mkdir -p -- "$CARGO_HOME" "$CARGO_TARGET_DIR"

manifest_source() {
    (
        cd "$repo_root"
        # In checkout mode the manifest must be reproducible from
        # source_commit, so hash tracked files only. An -uu scan also picks up
        # ignored paths (__pycache__, *.rs.bk) that leave the clean-tree gate
        # satisfied yet change the recorded hashes.
        if [[ "$source_commit_verification" == git-checkout ]]; then
            git ls-files -z
        else
            rg --no-config --files -uu -g '!/.git/' -g '!/target/' -0
        fi \
            | LC_ALL=C sort -z \
            | xargs -0 sha256sum --
    )
}
manifest_source >"$output_dir/source-files.before.sha256"

start_utc="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
{
    printf 'run_start_utc=%s\n' "$start_utc"
    printf 'runtime_alias=%s\n' "${RUNTIME_HOST_ALIAS:-unrecorded}"
    printf 'resolved_host=%s\n' "$(uname -n)"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-unknown}"
    printf 'selected_cpu=%s\n' "$cpu"
    printf 'cpus_allowed_list=%s\n' \
        "$(rg --no-config -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf 'page_size=%s\n' "$(getconf PAGESIZE)"
    printf 'perf_event_paranoid=%s\n' \
        "$(rg --no-config -m 1 '^-?[0-9]+$' /proc/sys/kernel/perf_event_paranoid)"
    printf '\naffinity\n'
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg --no-config -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo
    printf '\ngcc\n'
    gcc --version
    gcc -dumpmachine
    gcc -dumpfullversion
    printf '\nrustc\n'
    (cd "$repo_root" && rustc -vV)
    printf '\ncargo\n'
    (cd "$repo_root" && cargo -vV)
    printf '\npython\n'
    python3 --version
    printf '\ntarget_cfg\n'
    (cd "$repo_root" && rustc --print cfg -C target-cpu=native)
    printf '\nbinutils\n'
    objdump --version
    readelf --version
    printf '\nperf\n'
    perf version
} >"$output_dir/host.txt" 2>&1
gcc -march=native -Q --help=target >"$output_dir/gcc-native-target.txt" 2>&1
perf list >"$output_dir/perf-list.txt" 2>&1

gcc_flags=(
    -std=c11
    -O3
    -g
    -fno-lto
    -fno-pie
    -no-pie
    -fno-omit-frame-pointer
    -fno-optimize-sibling-calls
    -fno-toplevel-reorder
    -march=native
    # build_dir is a fresh mktemp path per run, and -g embeds the source path in
    # DWARF, so without this the same source produced a different ELF hash on
    # every run and the retained artifact-identity hashes could not be
    # reproduced. Map the scratch path to a fixed placeholder instead.
    "-ffile-prefix-map=$frontend_dir=/topic19-build"
    -Wall
    -Wextra
    -Werror
)
{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-unknown}"
    printf 'cargo_home=%s\n' "$CARGO_HOME"
    printf 'cargo_target_dir=%s\n' "$CARGO_TARGET_DIR"
    printf 'swept_environment=%s\n' "${swept_variables[*]:-none}"
    printf 'gcc_dense='
    printf '%q ' gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 \
        frontend_layout.c -o dense16
    printf '\n'
    printf 'gcc_sparse='
    printf '%q ' gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 \
        frontend_layout.c -o sparse4096
    printf '\n'
    printf 'gcc_working_directory=%s\n' "$frontend_dir"
    printf 'resolved_tools\n'
    printf '%s\n' "${resolved_tools[@]}"
    printf 'timing=12 blocks; odd ABBA; even BAAB; 48 fresh processes; '
    printf 'warm_rounds=512; measure_rounds=8192\n'
    printf 'perf=4 blocks per event pass; odd ABBA; even BAAB; '
    printf 'whole-process counts; anchor group must run at least 99%%\n'
} >"$output_dir/build-flags.txt"

if [[ "$source_commit_verification" == git-checkout ]]; then
    (
        cd "$repo_root"
        git diff --check
    ) >"$gates_dir/git-diff-check.log" 2>&1
else
    printf '%s\n' \
        'status=not-applicable' \
        'reason=Git archives have no index or parent tree.' \
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
    cargo test --locked --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    cargo test --locked --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    cargo clippy --locked --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    cargo bench --locked --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    RUSTDOCFLAGS="-D warnings" cargo doc --locked --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1
(
    # -I implies -E, so PYTHONPYCACHEPREFIX would be ignored and py_compile
    # would write __pycache__ beside the sources, which the archive-mode
    # after-manifest then reports as a source change. -X survives -E.
    python3 -I -X pycache_prefix="$build_dir/pycache" -m py_compile \
        "$topic_dir/experiment/generate.py" \
        "$topic_dir/experiment/frontend_experiment.py"
    bash -n "$topic_dir/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

generated_c="$frontend_dir/frontend_layout.c"
dense="$frontend_dir/dense16"
sparse="$frontend_dir/sparse4096"
aa_a="$frontend_dir/identical-a"
aa_b="$frontend_dir/identical-b"
python3 -I "$topic_dir/experiment/generate.py" "$generated_c"
# Compile from inside frontend_dir with a relative source name. -g records the
# compilation directory in DWARF, so invoking gcc from the caller's directory made
# the ELF bytes depend on that directory even with the source path mapped. Running
# here means the compilation directory is frontend_dir, which -ffile-prefix-map
# already rewrites to the fixed placeholder.
(
    cd "$frontend_dir"
    gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 frontend_layout.c -o dense16
    gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 frontend_layout.c -o sparse4096
)
ln "$dense" "$aa_a"
ln "$dense" "$aa_b"
{
    sha256sum "$generated_c" "$dense" "$sparse" "$aa_a" "$aa_b"
    stat -c 'path=%n device=%d inode=%i links=%h size=%s' \
        "$dense" "$aa_a" "$aa_b"
} >"$output_dir/artifact-identity.txt"
if [[ "$(stat -c '%d:%i' "$dense")" != "$(stat -c '%d:%i' "$aa_a")" ]] \
    || [[ "$(stat -c '%d:%i' "$dense")" != "$(stat -c '%d:%i' "$aa_b")" ]]; then
    printf 'identical-artifact controls are not hard links\n' >&2
    exit 1
fi

for variant in dense16 sparse4096; do
    binary="$frontend_dir/$variant"
    size -A "$binary" >"$output_dir/$variant.size.txt"
    readelf -SW "$binary" >"$output_dir/$variant.sections.txt"
    readelf -lW "$binary" >"$output_dir/$variant.program-headers.txt"
    nm -nS --defined-only "$binary" >"$output_dir/$variant.symbols.txt"
    objdump -drwC --no-show-raw-insn "$binary" \
        | gzip -n >"$output_dir/$variant.objdump.txt.gz"
    : >"$output_dir/$variant.focused-disassembly.txt"
    for symbol in leaf_0 leaf_511 run_rounds; do
        objdump -drwC --no-show-raw-insn --disassemble="$symbol" "$binary" \
            >>"$output_dir/$variant.focused-disassembly.txt"
    done
done

if ! perf stat -x ';' --no-big-num -o "$output_dir/perf-probe.csv" \
    -e task-clock -- true \
    >"$output_dir/perf-probe.stdout" \
    2>"$output_dir/perf-probe.stderr"; then
    printf 'perf task-clock probe failed\n' >&2
    exit 1
fi

python3 -I "$topic_dir/experiment/frontend_experiment.py" \
    --dense "$dense" \
    --sparse "$sparse" \
    --aa-a "$aa_a" \
    --aa-b "$aa_b" \
    --output-dir "$experiment_dir" \
    --cpu "$cpu" \
    >"$output_dir/process.log" 2>&1

manifest_source >"$output_dir/source-files.after.sha256"
if ! cmp -s \
    "$output_dir/source-files.before.sha256" \
    "$output_dir/source-files.after.sha256"; then
    printf 'source files changed during evidence collection\n' >&2
    exit 1
fi

printf 'run_end_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    >>"$output_dir/host.txt"
manifest_tmp="$(mktemp -p "$build_dir")"
(
    cd "$output_dir"
    rg --no-config --files -uu -0 . | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
