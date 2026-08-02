#!/usr/bin/env bash
set -euo pipefail

# Collect Topic 19 frontend-layout evidence on a Linux host.
#
# Scope, stated up front because it bounds every check below: this runner keeps a
# *measurement* honest. It is not an attestation apparatus. Every guard here
# answers one of exactly two questions:
#
#   1. Did I measure what I think I measured?
#      -- toolchain pin, swept codegen variables, recorded flags, CPU pinning,
#         before/after source manifest, hard-linked A/A control
#   2. Can I tell later what produced these numbers?
#      -- host.txt, build-flags.txt, ELF hashes and layout dumps, evidence.sha256
#
# It deliberately does NOT try to make the run unforgeable against a hostile
# environment. Anyone who can set RUSTFLAGS or shim gcc on the measuring host can
# equally edit the retained evidence afterwards, so checks aimed at that threat
# buy nothing here while adding surface that obscures the measurement logic. If
# you find yourself adding a guard, first say which of the two questions above it
# answers; if it answers neither, it does not belong in this file.

# ---------------------------------------------------------------------------
# Environment hygiene
# ---------------------------------------------------------------------------
# These variables change what the compilers actually do -- which toolchain runs,
# which flags it gets, which headers and libraries it finds, what Python imports
# -- or change how perf collects counters. Left in place, build-flags.txt would
# describe a build that did not happen. Clear them and record what was cleared,
# so a run made under a stray RUSTFLAGS is visible in the evidence instead of
# being silently folded into the numbers.
swept_variables=()
while IFS= read -r variable; do
    case "$variable" in
        CARGO_* | GIT_* | LD_* \
            | RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTC_BOOTSTRAP \
            | RUSTDOC | RUSTDOCFLAGS | RUSTFLAGS | RUSTFMT \
            | RUSTUP_TOOLCHAIN | RUSTUP_HOME | CLIPPY_CONF_DIR \
            | RIPGREP_CONFIG_PATH \
            | CPATH | C_INCLUDE_PATH | CPLUS_INCLUDE_PATH | OBJC_INCLUDE_PATH \
            | COMPILER_PATH | GCC_EXEC_PREFIX | GCC_COMPARE_DEBUG \
            | LIBRARY_PATH | DEPENDENCIES_OUTPUT | SUNPRO_DEPENDENCIES \
            | CDPATH | PERF_CONFIG \
            | PYTHONPATH | PYTHONHOME | PYTHONSTARTUP)
            swept_variables+=("$variable")
            unset "$variable"
            ;;
    esac
done < <(compgen -e)
# perf falls back to $HOME/.perfconfig when PERF_CONFIG is unset, and perf stat
# settings there change how the measured events are collected. Point it at an
# empty file so neither source applies.
export PERF_CONFIG=/dev/null

# ---------------------------------------------------------------------------
# Arguments
# ---------------------------------------------------------------------------
if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/019-cpu-frontend-bottlenecks"
topic_dir="$repo_root/$topic_rel"

if [[ ! -r "$topic_dir/experiment/generate.py" ]] \
    || [[ ! -r "$topic_dir/experiment/frontend_experiment.py" ]]; then
    printf 'repository lacks the Topic 19 experiment\n' >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Output directory
# ---------------------------------------------------------------------------
# The evidence directory must live outside the repository. This is a practical
# constraint, not a security one: the root workspace globs `topics/*`, so a
# directory created under it becomes a workspace member with no manifest and
# every later Cargo invocation fails to load. Check the absolute path before
# mkdir so the common mistake does not leave the repo broken, then re-check the
# resolved path afterwards to catch a symlinked target.
case "$output_dir" in
    /*) candidate_output="$output_dir" ;;
    *) candidate_output="$PWD/$output_dir" ;;
esac
if [[ "$candidate_output" == "$repo_root" || "$candidate_output" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository: %s\n' "$output_dir" >&2
    exit 2
fi
if [[ -e "$output_dir" && ! -d "$output_dir" ]]; then
    printf 'OUTPUT_DIRECTORY exists and is not a directory: %s\n' "$output_dir" >&2
    exit 2
fi
mkdir -p -- "$output_dir"
output_dir="$(cd -- "$output_dir" && pwd -P)"
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository: %s\n' "$output_dir" >&2
    exit 2
fi
# A non-empty directory would mix this run's evidence with a previous one, and
# evidence.sha256 at the end would cover both without distinguishing them.
shopt -s nullglob dotglob
existing_entries=("$output_dir"/*)
shopt -u nullglob dotglob
if ((${#existing_entries[@]} > 0)); then
    printf 'OUTPUT_DIRECTORY must be empty: %s\n' "$output_dir" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Required tools
# ---------------------------------------------------------------------------
required_tools=(
    awk cargo cc cmp date gcc getconf git gzip ln lscpu mkdir mktemp mv nm
    objdump perf python3 readelf rg rm rustc sha256sum size sort stat taskset
    uname xargs
)
for tool in "${required_tools[@]}"; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done
# Record where each tool resolved. A surprising answer (a wrapper, a second gcc
# earlier on PATH) is then visible when reading the evidence months later, which
# is the question this answers -- not tamper detection.
recorded_tools=()
for tool in "${required_tools[@]}"; do
    recorded_tools+=("$(printf '%s %s' "$tool" "$(command -v "$tool")")")
done
recorded_tools+=("$(printf 'effective_rustup_home %s' "${RUSTUP_HOME:-$HOME/.rustup}")")
recorded_tools+=("$(printf 'perf_config %s' "$PERF_CONFIG")")

# ---------------------------------------------------------------------------
# CPU selection
# ---------------------------------------------------------------------------
# Everything measured runs pinned to one CPU, and -march=native below resolves
# from whichever CPU the compiler runs on, so the same CPU has to be used for
# both or the recorded flags describe a different core than the one measured.
if (($# == 3)); then
    cpu="$3"
else
    allowed="$(rg --no-config -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
    first="${allowed%%,*}"
    cpu="${first%%-*}"
fi
if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]] \
    || ! taskset -c "$cpu" uname >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
    exit 2
fi

# ---------------------------------------------------------------------------
# Source identity
# ---------------------------------------------------------------------------
# Two modes. A Git checkout names its own commit and must be clean, so the
# evidence can say exactly which bytes were compiled. An extracted Git archive
# has no index, so the caller declares the identity and the evidence labels it
# declared rather than verified.
#
# Assignments from command substitution abort under `set -e`, so a git failure
# here cannot be mistaken for a clean tree.
if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" == "$repo_root" ]]; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    source_commit_verification=git-checkout
    # --untracked-files=all so a repository-level status.showUntrackedFiles
    # setting cannot hide a stray file that the Cargo gates would compile.
    worktree_status="$(git -C "$repo_root" status --porcelain --untracked-files=all)"
    if [[ -n "$worktree_status" ]]; then
        printf 'repository must be clean; measured bytes would not match %s\n' \
            "$source_commit" >&2
        printf '%s\n' "$worktree_status" >&2
        exit 2
    fi
    if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
        printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
        exit 2
    fi
    # A tracked symbolic link puts the link in the index while the manifest below
    # hashes what the link resolves to -- sha256sum follows links -- so a link
    # pointing outside the tree would attribute foreign bytes to source_commit.
    # One index read answers this. Walking the worktree is not needed and would
    # traverse .git and target/ to reach the same conclusion.
    tracked_symlinks="$(git -C "$repo_root" ls-files -s | awk '$1 == "120000"')"
    if [[ -n "$tracked_symlinks" ]]; then
        printf 'tracked symbolic links are unsupported: the manifest would hash\n' >&2
        printf 'the link target rather than the recorded source bytes:\n%s\n' \
            "$tracked_symlinks" >&2
        exit 2
    fi
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

# ---------------------------------------------------------------------------
# Toolchain pin
# ---------------------------------------------------------------------------
# This is the one pin that materially changes the measurement: a different rustc
# or gcc emits different code, and this topic is about the shape of emitted code.
# rustup gives the extensionless legacy file precedence when both exist, so the
# effective pin is selected the same way.
if [[ -e "$repo_root/rust-toolchain" ]]; then
    pin_file="$repo_root/rust-toolchain"
elif [[ -e "$repo_root/rust-toolchain.toml" ]]; then
    pin_file="$repo_root/rust-toolchain.toml"
else
    pin_file=""
fi
if [[ -n "$pin_file" ]]; then
    pinned_channel_line="$(
        rg --no-config -m 1 '^[[:space:]]*channel[[:space:]]*=' "$pin_file" \
            2>/dev/null || true
    )"
    if [[ -n "$pinned_channel_line" ]]; then
        pinned_channel="${pinned_channel_line#*\"}"
        pinned_channel="${pinned_channel%%\"*}"
        [[ "$pinned_channel" == "$pinned_channel_line" ]] && pinned_channel=""
    else
        # A legacy file with no channel key is a bare toolchain name on one line.
        pinned_channel="$(
            rg --no-config -m 1 -v '^[[:space:]]*$' "$pin_file" 2>/dev/null || true
        )"
        pinned_channel="${pinned_channel#"${pinned_channel%%[![:space:]]*}"}"
        pinned_channel="${pinned_channel%"${pinned_channel##*[![:space:]]}"}"
        case "$pinned_channel" in
            *'='* | *'['*) pinned_channel="" ;;
        esac
    fi
    if [[ -z "$pinned_channel" ]]; then
        printf 'could not read the pinned toolchain channel from %s\n' "$pin_file" >&2
        exit 2
    fi
    recorded_tools+=("$(printf 'pin_file %s' "${pin_file#"$repo_root"/}")")
    # Verify the outcome rather than the mechanism: whatever cargo and rustc the
    # gates will actually run must report the pinned channel.
    for pinned_tool in cargo rustc; do
        pinned_version="$(cd "$repo_root" && "$pinned_tool" --version)"
        if [[ "$pinned_version" != *"$pinned_channel"* ]]; then
            printf 'the %s the gates would use does not match the pinned %s\n' \
                "$pinned_tool" "$pinned_channel" >&2
            printf 'reported: %s\n' "$pinned_version" >&2
            exit 2
        fi
        recorded_tools+=("$(printf 'pinned-%s-version %s' "$pinned_tool" "$pinned_version")")
    done
fi

# ---------------------------------------------------------------------------
# Scratch tree
# ---------------------------------------------------------------------------
build_dir="$(mktemp -d)"
build_dir="$(cd -- "$build_dir" && pwd -P)"
# Scratch inside the evidence directory would be hashed by the final manifest and
# then deleted, leaving evidence.sha256 describing files the archive lacks.
# Scratch inside the repository becomes a workspace member and breaks the gates.
if [[ "$build_dir" == "$output_dir" \
    || "$build_dir" == "$output_dir"/* \
    || "$output_dir" == "$build_dir"/* \
    || "$build_dir" == "$repo_root" \
    || "$build_dir" == "$repo_root"/* \
    || "$repo_root" == "$build_dir"/* ]]; then
    printf 'refusing to place the build tree inside the evidence or source tree\n' >&2
    printf 'set TMPDIR outside OUTPUT_DIRECTORY and the repository\n' >&2
    rm -rf -- "$build_dir"
    exit 1
fi
manifest_tmp=
cleanup() {
    rm -rf -- "$build_dir"
    # An `if` rather than `[[ ... ]] && rm`: under `set -e` a false test as the
    # last command in an EXIT trap makes the trap return nonzero, which becomes
    # the script's exit status -- reporting failure for a run that fully
    # succeeded. `return 0` for the same reason.
    if [[ -n "$manifest_tmp" ]]; then
        rm -f -- "$manifest_tmp"
    fi
    return 0
}
trap cleanup EXIT

gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
frontend_dir="$build_dir/frontend"
mkdir -p -- "$gates_dir" "$frontend_dir"

# An isolated CARGO_HOME and target dir keep the gates from depending on, or
# writing into, whatever state the host's Cargo cache happens to hold.
export CARGO_HOME="$build_dir/cargo-home"
export CARGO_TARGET_DIR="$build_dir/cargo-target"
mkdir -p -- "$CARGO_HOME" "$CARGO_TARGET_DIR"

# ---------------------------------------------------------------------------
# Source manifest, before
# ---------------------------------------------------------------------------
# Hashed before and after the run and compared at the end. This catches the
# realistic failure -- editing the tree while a multi-minute run is in flight, so
# the numbers and the recorded source disagree.
manifest_source() {
    (
        cd "$repo_root"
        # Checkout mode hashes tracked files only, so the manifest is
        # reproducible from source_commit. An -uu scan would also pick up ignored
        # paths (__pycache__, *.rs.bk) that change the hashes while leaving the
        # clean-tree check satisfied.
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
# A digest over that manifest is a single value identifying the bytes this run
# compiled, computed here rather than taken from the caller. In archive mode the
# declared commit and archive hash are unverifiable, so this is the value to
# compare between runs or against a known tree.
source_tree_digest="$(sha256sum -- "$output_dir/source-files.before.sha256")"
recorded_tools+=("$(printf 'source_tree_digest %s' "${source_tree_digest%% *}")")

# ---------------------------------------------------------------------------
# Host and toolchain record
# ---------------------------------------------------------------------------
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
# -march=native resolves from the CPU the compiler happens to run on, so pin this
# to the same CPU the measured processes use.
taskset -c "$cpu" gcc -march=native -Q --help=target \
    >"$output_dir/gcc-native-target.txt" 2>&1
perf list >"$output_dir/perf-list.txt" 2>&1

# ---------------------------------------------------------------------------
# Build flags
# ---------------------------------------------------------------------------
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
    # build_dir is a fresh mktemp path per run and -g embeds the source path in
    # DWARF, so without this the same source produced a different ELF hash every
    # run and the recorded artifact identities could not be reproduced.
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
    printf '%q ' taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 \
        frontend_layout.c -o dense16
    printf '\n'
    printf 'gcc_sparse='
    printf '%q ' taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 \
        frontend_layout.c -o sparse4096
    printf '\n'
    printf 'gcc_working_directory=%s\n' "$frontend_dir"
    printf 'recorded_tools\n'
    printf '%s\n' "${recorded_tools[@]}"
    printf 'timing=12 blocks; odd ABBA; even BAAB; 48 fresh processes; '
    printf 'warm_rounds=512; measure_rounds=8192\n'
    printf 'perf=4 blocks per event pass; odd ABBA; even BAAB; '
    printf 'whole-process counts; anchor group must run at least 99%%\n'
} >"$output_dir/build-flags.txt"

# ---------------------------------------------------------------------------
# Workspace gates
# ---------------------------------------------------------------------------
# The repo's own health checks. Retained as logs so a later reader can see the
# tree was in a known-good state when the numbers were taken.
if [[ "$source_commit_verification" == git-checkout ]]; then
    (cd "$repo_root" && git diff --check) >"$gates_dir/git-diff-check.log" 2>&1
else
    printf '%s\n' \
        'status=not-applicable' \
        'reason=Git archives have no index or parent tree.' \
        "source_commit=$source_commit" \
        "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
        >"$gates_dir/git-diff-check.log"
fi
(cd "$repo_root" && cargo fmt --all -- --check) \
    >"$gates_dir/cargo-fmt.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --lib --examples) \
    >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --doc) \
    >"$gates_dir/cargo-test-doc.log" 2>&1
(cd "$repo_root" && cargo clippy --locked --workspace --all-targets -- -D warnings) \
    >"$gates_dir/cargo-clippy.log" 2>&1
(cd "$repo_root" && cargo bench --locked --workspace --no-run) \
    >"$gates_dir/cargo-bench-no-run.log" 2>&1
(cd "$repo_root" && RUSTDOCFLAGS="-D warnings" cargo doc --locked --workspace --no-deps) \
    >"$gates_dir/cargo-doc.log" 2>&1
(
    # -I implies -E, so PYTHONPYCACHEPREFIX would be ignored and py_compile would
    # write __pycache__ beside the sources, which the after-manifest then reports
    # as a source change. -X survives -E.
    python3 -I -X pycache_prefix="$build_dir/pycache" -m py_compile \
        "$topic_dir/experiment/generate.py" \
        "$topic_dir/experiment/frontend_experiment.py"
    bash -n "$topic_dir/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

# ---------------------------------------------------------------------------
# Build the two layout variants
# ---------------------------------------------------------------------------
generated_c="$frontend_dir/frontend_layout.c"
dense="$frontend_dir/dense16"
sparse="$frontend_dir/sparse4096"
aa_a="$frontend_dir/identical-a"
aa_b="$frontend_dir/identical-b"
python3 -I "$topic_dir/experiment/generate.py" "$generated_c"
# Compile from inside frontend_dir with a relative source name. -g records the
# compilation directory in DWARF, so invoking gcc from the caller's directory made
# the ELF bytes depend on that directory even with the source path mapped. Running
# here makes the compilation directory frontend_dir, which -ffile-prefix-map
# already rewrites to a fixed placeholder.
(
    cd "$frontend_dir"
    taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 \
        frontend_layout.c -o dense16
    taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 \
        frontend_layout.c -o sparse4096
)
# The A/A control is two hard links to one ELF, so the two arms are byte- and
# inode-identical by construction. Any measured difference between them is
# label, launch-path, or analysis asymmetry rather than a layout effect.
ln "$dense" "$aa_a"
ln "$dense" "$aa_b"
{
    sha256sum "$generated_c" "$dense" "$sparse" "$aa_a" "$aa_b"
    stat -c 'path=%n device=%d inode=%i links=%h size=%s' "$dense" "$aa_a" "$aa_b"
} >"$output_dir/artifact-identity.txt"
if [[ "$(stat -c '%d:%i' "$dense")" != "$(stat -c '%d:%i' "$aa_a")" ]] \
    || [[ "$(stat -c '%d:%i' "$dense")" != "$(stat -c '%d:%i' "$aa_b")" ]]; then
    printf 'identical-artifact controls are not hard links\n' >&2
    exit 1
fi

# ---------------------------------------------------------------------------
# Layout evidence
# ---------------------------------------------------------------------------
# This is the substance of the topic: what the two binaries actually look like.
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

# ---------------------------------------------------------------------------
# Measure
# ---------------------------------------------------------------------------
# Fail early and loudly if perf cannot count at all, rather than producing a run
# full of zeros that reads like an absence of activity.
if ! perf stat -x ';' --no-big-num -o "$output_dir/perf-probe.csv" \
    -e task-clock -- uname \
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

# ---------------------------------------------------------------------------
# Source manifest, after
# ---------------------------------------------------------------------------
manifest_source >"$output_dir/source-files.after.sha256"
if ! cmp -s \
    "$output_dir/source-files.before.sha256" \
    "$output_dir/source-files.after.sha256"; then
    printf 'source files changed during evidence collection\n' >&2
    exit 1
fi

printf 'run_end_utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
    >>"$output_dir/host.txt"
# The manifest is built in scratch and moved into place, so a run interrupted
# mid-hash does not leave a partial evidence.sha256 that looks complete.
manifest_tmp="$(mktemp -p "$build_dir")"
(
    cd "$output_dir"
    rg --no-config --files -uu -0 . | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"
manifest_tmp=

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
