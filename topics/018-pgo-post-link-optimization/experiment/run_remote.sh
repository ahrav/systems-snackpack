#!/usr/bin/env bash
set -euo pipefail

# Validates an exact Linux source tree, runs Topic 18, and writes evidence
# outside the repository.

# Refuse a startup file rather than clearing one. This runs before the restart
# below because the restart is already too late: an ordinary non-interactive Bash
# sources `BASH_ENV` before line one, so by the time any branch here executes the
# hook has run, and it can export a `PATH` and `set --` the repository and output
# arguments the restart then forwards. Unsetting the variable at that point
# removes the only remaining record that unattributed code chose this run's
# inputs, leaving receipts that name hook-selected tools and paths. A hostile hook
# can unset the variable itself, which is why the documented invocation is
# `bash -p` — privileged mode never sources it, and the value stays visible here
# to be refused. This check covers what remains visible and never destroys it.
#
# `builtin printf` because this is the one check that can run in an unprivileged
# shell, where an imported function answers ahead of the builtin.
for startup_variable in BASH_ENV ENV; do
    if [[ -n "${!startup_variable:-}" ]]; then
        builtin printf '%s\n' \
            "shell startup file must not be set: $startup_variable=${!startup_variable}" \
            "it is sourced before this script runs and no receipt records it" >&2
        exit 2
    fi
done

# Restart once in a shell that carries none of the caller's shell state. Bash
# sources `BASH_ENV` before the first line of a non-interactive script, and a
# hook can install traps, define functions, prepend a directory to `PATH`, and
# replace the positional arguments — so the restart cannot undo what already ran,
# and a `PATH` lookup for the relaunch could find a planted `bash`. Replacing the
# process image discards traps and shell options, and `/proc/self/exe` is the
# running interpreter rather than a name resolved through a `PATH` the hook may
# already own.
#
# `-p` is what stops the next shell importing the caller's functions: privileged
# mode does not process `BASH_ENV` or `ENV`, does not inherit functions from the
# environment, and ignores an inherited `SHELLOPTS`, `BASHOPTS`, `CDPATH`, or
# `GLOBIGNORE`. That matters because an imported `command` or `git` function
# answers before any builtin or program, so it can forge `rev-parse`, `status`,
# and `archive` output and with it the source provenance. Stripping the function
# names cannot substitute for it: the strip reads the list through `builtin
# declare -F`, and an imported function named `builtin` answers that call, hides
# every name from both the loop and the survivor check below, and leaves the
# forging functions defined. The strip stays because it also covers a caller who
# shadows only `git` or `command`, but `-p` is the part that holds when the
# shadow reaches the shell's own vocabulary.
#
# An imported `exec` function is dispatched ahead of the builtin too, so a caller
# who shadows `exec` skips this restart entirely and no in-script test placed
# after it can prove otherwise. Closing that requires a launcher outside this
# process image, which is why the documented invocation starts Bash with `-p`.
# Branch on privileged mode itself, not on the marker. A caller who exports
# `TOPIC18_REEXECED=1` would otherwise skip the only `exec ... -p` and run the
# whole body in an ordinary shell, where an imported `builtin` hides
# `builtin declare -F` from the survivor check below and an imported `git`
# answers the provenance commands. `[[ -o privileged ]]` reads the option the
# restart exists to obtain, and `[[` is a shell keyword rather than a builtin, so
# no imported function can answer it. The marker now only prevents a restart loop:
# reaching this point unprivileged after a restart means `-p` did not take, which
# is a refusal rather than a second attempt.
if [[ ! -o privileged ]]; then
    if [[ -n "${TOPIC18_REEXECED:-}" ]]; then
        printf '%s\n' \
            "restarted without privileged mode" \
            "TOPIC18_REEXECED is set but this shell is not privileged, so the" \
            "caller's shell functions and startup files were not excluded" >&2
        exit 2
    fi
    while read -r _ _ imported_function; do
        unset -f "$imported_function"
    done < <(builtin declare -F)
    export TOPIC18_REEXECED=1
    exec /proc/self/exe -p -- "$0" "$@"
fi
# Nothing should be defined yet; this script declares its own functions further
# down. A survivor means neither `-p` nor the strip above took effect as written.
if [[ -n "$(builtin declare -F)" ]]; then
    printf '%s\n' \
        "shell functions were imported into this run:" \
        "$(builtin declare -F)" \
        "an imported function answers before a builtin or program, including the" \
        "tool resolution and provenance commands below" >&2
    exit 2
fi
# Privileged mode declines to import the caller's functions, but the
# `BASH_FUNC_name%%` entries carrying them stay in this process's environment and
# are inherited by everything it runs. `compgen -e` cannot report them — the names
# are not valid shell identifiers — so the namespace sweep below never sees them,
# and any tool that is itself a Bash script starts a non-privileged shell that
# imports them: a wrapper `git` delegating to `git "$@"` would answer from the
# caller's function while this run recorded only the wrapper's digest. Read the raw
# environment instead, which is the only place these are visible.
raw_environment_functions=()
while IFS= read -r -d '' raw_environment_entry; do
    case "$raw_environment_entry" in
        BASH_FUNC_*) raw_environment_functions+=("${raw_environment_entry%%=*}") ;;
    esac
done <"/proc/$$/environ"
if ((${#raw_environment_functions[@]} > 0)); then
    printf '%s\n' \
        "exported shell functions remain in the environment:" \
        "${raw_environment_functions[@]}" \
        "privileged mode does not import them here, but any tool that is a Bash" \
        "script starts a shell that does, and no receipt records them" >&2
    exit 2
fi

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
input_root="$repo_root"
output_dir="$2"
topic_rel="topics/018-pgo-post-link-optimization"
topic_dir="$repo_root/$topic_rel"

# A `PATH` entry that is empty, `.`, or otherwise relative names the current
# directory, so an unqualified `git` or `tar` would resolve against whatever
# directory this script happens to be in — including the source tree it is about
# to attest to. `command -v` reports such a hit as a real program. Split with
# parameter expansion rather than a here-string, which would append a newline and
# report a trailing entry the variable does not contain.
path_remainder="$PATH"
while :; do
    path_entry="${path_remainder%%:*}"
    if [[ "$path_entry" != /* ]]; then
        printf '%s\n' \
            "PATH entry is not absolute: ${path_entry:-<empty>}" \
            "a relative or empty entry resolves tools against the current directory" >&2
        exit 2
    fi
    [[ "$path_remainder" == *:* ]] || break
    path_remainder="${path_remainder#*:}"
done

declare -A tool_path=()
for required in \
    awk bash cargo cc clippy-driver cmp cp date diff env getconf git ld lscpu mkdir \
    mktemp mv nm objdump python3 rg rm rustc rustfmt rustup sed sha256sum sort \
    tar taskset uname xargs; do
    # Require a program, not merely a name that resolves. An exported shell
    # function — `export -f git` arrives as a `BASH_FUNC_git%%` environment entry
    # — satisfies a bare `command -v` and then answers every unqualified call, so
    # a caller could forge `rev-parse`, `status`, or `archive` output and with it
    # the whole source provenance. Aliases and builtins shadow the same way. Only
    # a program resolves to an absolute path.
    #
    # Resolving to a program is not the same as resolving to a trusted one:
    # `command -v` reports the command lookup path, so a caller-writable `PATH`
    # entry holding an executable `git` satisfies this check and then answers
    # `rev-parse`, `status`, `archive`, and `ls-tree`. No path test separates that
    # from a legitimate tool, because the toolchain programs themselves live
    # outside the system directories — `cargo`, `rustc`, `rustup`, `rustfmt`,
    # `clippy-driver`, and `rg` normally resolve under a user-owned `~/.cargo/bin`.
    # Record the resolved path and digest of every tool instead, so the retained
    # evidence names the binaries that produced it and an auditor can compare them
    # against the host rather than trusting the run's own `PATH`.
    resolved_required="$(command -v "$required" || true)"
    if [[ "$resolved_required" != /* ]]; then
        printf '%s\n' \
            "required executable is not a program: $required -> ${resolved_required:-not found}" \
            "a shell function, alias, or builtin shadowing a tool would forge its output" >&2
        exit 2
    fi
    tool_path["$required"]="$resolved_required"
done
# Digest every resolved tool before any of them runs. Hashing at receipt time
# instead would record whatever the file holds after the provenance work: a
# script `git` could forge `rev-parse`, `status`, and `archive`, then be replaced
# by the real program, and the receipt would attest a benign digest for a binary
# that produced none of the evidence. This pass needs `sha256sum`, which is itself
# resolved above, so it cannot fold into that loop. The digests are compared again
# where the receipt is written, and a change between the two reads fails the run.
#
# This attestation is self-referential and cannot be made otherwise from inside
# the run: `sha256sum` and `awk` are resolved the same way as everything else, so
# a `PATH` that supplies a fake `sha256sum` supplies the program that reports the
# digests, and it can print the real binaries' digests for itself and for the
# other fakes. No in-script ordering fixes that, because every candidate anchor is
# reached through the same lookup. What the receipt gives an auditor is the
# resolved paths and `PATH` itself, which is why both are recorded verbatim: the
# digests are checkable only against a trusted copy of those tools obtained
# outside this run, and a tool resolved from an unexpected directory is visible
# even when its digest cannot be trusted.
declare -A tool_digest=()
for digested_tool in "${!tool_path[@]}"; do
    tool_digest["$digested_tool"]="$(
        "${tool_path[sha256sum]}" -- "${tool_path[$digested_tool]}" | "${tool_path[awk]}" '{print $1}'
    )"
done
# Bind a program resolved later than the loop above, before the run uses it. The
# rustup entries resolved above are the proxies on `PATH`; the gates and the driver
# execute the toolchain binaries the proxies dispatch to, which are different files
# with different digests, so recording only the proxies leaves the compiler that
# validates the snapshot and produces the measured binaries unbound.
# A `PATH` built from the directories the resolved tools actually live in, and nothing
# else. Appending the caller's `PATH` would leave every lookup a fallback: `env` resolves
# the command operand through the `PATH` it is given, and `cc` falls through `-B`, its
# standard prefixes, and then `PATH` when it looks for `ld` — so a bound program hidden
# after its digest is taken would be replaced by a later entry rather than failing the run.
# With only these directories present there is nowhere to fall through to, so a missing
# program is an error instead of a substitution.
bound_tool_path() {
    local -A seen=()
    local ordered=() directory extra key
    local -a prefixes=() keys=()
    local collecting=prefixes
    for extra in "$@"; do
        if [[ "$extra" == -- ]]; then
            collecting=keys
            continue
        fi
        if [[ "$collecting" == prefixes ]]; then
            prefixes+=("$extra")
        else
            keys+=("$extra")
        fi
    done
    for extra in "${prefixes[@]}"; do
        if [[ -n "$extra" && -z "${seen[$extra]:-}" ]]; then
            seen["$extra"]=1
            ordered+=("$extra")
        fi
    done
    # Naming keys restricts the directories to the tools a caller actually needs. The
    # rustup proxies resolve under a user-owned prefix, and the gates use the toolchain's
    # own bin directory instead, so including that prefix would leave `cargo fmt` and
    # `cargo clippy` a fall-through for their `cargo-*` helpers.
    if ((${#keys[@]} == 0)); then
        keys=("${!tool_path[@]}")
    fi
    for key in "${keys[@]}"; do
        directory="${tool_path[$key]%/*}"
        if [[ -n "$directory" && -z "${seen[$directory]:-}" ]]; then
            seen["$directory"]=1
            ordered+=("$directory")
        fi
    done
    local joined="" entry
    for entry in "${ordered[@]}"; do
        joined+="${joined:+:}$entry"
    done
    printf '%s' "$joined"
}
digest_tool() {
    tool_path["$1"]="$2"
    tool_digest["$1"]="$("${tool_path[sha256sum]}" -- "$2" | "${tool_path[awk]}" '{print $1}')"
}
# The driver probes these after the timings but before it writes
# `binary-sha256.json`, so executing one taken from `PATH` runs unrecorded code
# while the retained files are still being produced. They are genuinely optional, so
# bind the ones that resolve to a program and leave the rest unbound; the driver
# records availability for an unbound tool without executing it.
for optional_tool in llvm-bolt perf2bolt merge-fdata perf; do
    resolved_optional="$(command -v "$optional_tool" || true)"
    if [[ "$resolved_optional" == /* ]]; then
        digest_tool "$optional_tool" "$resolved_optional"
    fi
done
# `-I` isolates the probe from the caller's Python startup environment. A bare
# `python3` imports `sitecustomize` from a `PYTHONPATH` directory and runs it
# before this script has checked anything or verified any source, so the hook
# could edit the checkout, the archive, or the tools with no receipt of it. The
# gates and the driver already run `-I` for the same reason.
"${tool_path[python3]}" -I -c 'import sys; raise SystemExit(sys.version_info < (3, 8))'
# Loader and libc state reaches every timed child through the driver: `LD_PRELOAD`
# and `LD_AUDIT` can interpose the calls being timed, `LD_DEBUG` adds diagnostic
# work to each startup, and `GLIBC_TUNABLES` and the older `MALLOC_*` knobs change
# allocator behaviour. Nothing in the retained provenance records it, so the rows
# would be attributed to the binary and host alone. Sweep the namespaces rather
# than name members: the loader and libc keep adding variables, and a list is a
# snapshot of the ones known when it was written. Clearing these could break a
# toolchain that relies on them, so refuse and let the operator present a
# controlled environment.
# Git's own repository environment redirects the provenance queries below. `GIT_DIR`
# and `GIT_WORK_TREE` are honoured by `git -C`, so a caller can point the object
# store at one repository while the work tree stays this source tree:
# `rev-parse --show-toplevel` still prints the given root and passes the check
# below, `status --porcelain` is clean whenever the bytes match, and `rev-parse
# HEAD` returns the other store's commit. The run then records
# `source_commit_verification=git-checkout` for a commit that no clone of this
# repository contains. `GIT_INDEX_FILE`, `GIT_OBJECT_DIRECTORY`,
# `GIT_ALTERNATE_OBJECT_DIRECTORIES`, `GIT_GRAFT_FILE`, and the `GIT_CONFIG*`
# entries redirect the same queries by other routes — `git rev-parse
# --local-env-vars` lists the current set — so sweep the namespace here for the
# same reason the loader namespaces are swept. The one member this script relies
# on is exported below, after this loop.
for caller_variable in $(compgen -e); do
    case "$caller_variable" in
        LD_* | GLIBC_* | MALLOC_*)
            printf '%s\n' \
                "loader environment must be unset for measurement: $caller_variable" \
                "every timed probe inherits it and no receipt records it" >&2
            exit 2
            ;;
        GIT_*)
            printf '%s\n' \
                "git repository environment must be unset: $caller_variable" \
                "it redirects the provenance queries below and no receipt records it" >&2
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
# no environment change reaches. `RUSTFLAGS` pins the linker driver for the same
# reason the experiment build passes `-Clinker`: with no flag, rustc links through
# whatever `cc` the prepended toolchain directory supplies, so a gate log could be
# produced by a driver the receipt does not name. The gates that link are
# `cargo test` and `cargo bench --no-run`; `fmt`, `clippy`, and `doc` ignore it.
gate_env() {
    # Rescan here, not only once before the gates. Every gate resolves `cargo` — and
    # `cargo fmt` and `cargo clippy` additionally resolve an external
    # `cargo-<command>` helper — through the `PATH` built below, so a program placed
    # in one of these directories after the earlier scan would answer for a bound
    # name. `require_unshadowed_gate_path` is defined further down but is only ever
    # called from here and from that scan, both of which run after its definition.
    require_unshadowed_gate_path
    "${tool_path[env]}" -i \
        PATH="$(bound_tool_path "$gate_toolchain_bin" -- \
            awk bash cc cmp cp date diff env getconf ld mkdir mktemp mv nm \
            objdump python3 rm sed sha256sum sort tar taskset uname xargs)" \
        HOME="$HOME" \
        LC_ALL=C \
        ${RUSTUP_HOME:+RUSTUP_HOME="$RUSTUP_HOME"} \
        CARGO_HOME="$gate_cargo_home" \
        CARGO_TARGET_DIR="$CARGO_TARGET_DIR" \
        CARGO_ENCODED_RUSTFLAGS="-Clinker=${tool_path[cc]}"$'\x1f'"-Clink-arg=-B$pinned_linker_dir/" \
        "$@"
}
# `git replace` refs and grafts are honoured by object reads, so `git archive`
# can emit a replacement tree while `rev-parse HEAD` still reports the original
# commit. The manifest would then reproduce from a local rewrite that a clone of
# `source_commit` does not contain. Read raw objects for every provenance query.
# The sweep above refuses a caller-supplied value, so this assignment is the only
# one the provenance commands see.
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
    "${tool_path[rustup]}" which --toolchain "$experiment_rustup_toolchain" rustc 2>/dev/null || true
)"
if [[ ! -x "$experiment_rustc" ]]; then
    printf 'rustup cannot resolve rustc for toolchain %s\n' \
        "$experiment_rustup_toolchain" >&2
    exit 2
fi
experiment_toolchain_bin="${experiment_rustc%/*}"
# Bind the compiler that builds the measured binaries, not the `PATH` proxy that
# dispatches to it.
digest_tool experiment_rustc "$experiment_rustc"
if [[ -x "$experiment_toolchain_bin/cargo" ]]; then
    digest_tool experiment_cargo "$experiment_toolchain_bin/cargo"
fi
# The driver resolves two more programs out of this toolchain's sysroot and runs
# them on the measured binaries, so `rustc` alone does not bind what produced them.
# `llvm-profdata` merges the training profiles that `-Cprofile-use` consumes, so a
# different profiler shapes the profile while `rustc` reads as unchanged; and
# `rust-lld` links the candidates on toolchains that default to it, so a swapped
# linker emits the timed image. The driver records their versions after building,
# which cannot detect a program restored before that probe. Both are optional
# components, so bind them when the toolchain ships them.
experiment_sysroot="$("$experiment_rustc" --print sysroot)"
experiment_host="$("$experiment_rustc" -vV | "${tool_path[sed]}" -n 's/^host: //p')"
experiment_rustlib_bin="$experiment_sysroot/lib/rustlib/$experiment_host/bin"
# Profile merging requires the bundled `llvm-profdata`, so its absence is a refusal
# here rather than something the driver discovers later. Binding it before anything runs
# is also what makes the digest cover the profiler that produced the PGO inputs.
if [[ ! -x "$experiment_rustlib_bin/llvm-profdata" ]]; then
    printf '%s\n' \
        "toolchain $experiment_rustup_toolchain lacks its bundled llvm-profdata:" \
        "$experiment_rustlib_bin/llvm-profdata" \
        "the driver merges the training profiles with it, so it must be present and" \
        "recorded before the run starts" >&2
    exit 2
fi
digest_tool experiment_llvm-profdata "$experiment_rustlib_bin/llvm-profdata"
# `rust-lld` is optional: a toolchain that links through the system linker ships none,
# and `cc` and `ld` are bound either way. Bind it when present.
if [[ -x "$experiment_rustlib_bin/rust-lld" ]]; then
    digest_tool experiment_rust-lld "$experiment_rustlib_bin/rust-lld"
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
# Decide whether the target is inside the repository before creating anything.
# `mkdir -p` followed by a check leaves the directory behind on the rejection path,
# because nothing owns it yet — the scratch trap is armed later and covers only the
# scratch tree — so a refused run would deposit a stray directory in the source tree
# it was refusing to write into. `pwd -P` needs an existing directory, so resolve the
# nearest ancestor that does exist and re-attach the components below it; that also
# catches a symlinked parent, which a textual prefix test on the argument would miss.
output_probe="$output_dir"
output_suffix=""
while [[ ! -d "$output_probe" ]]; do
    output_component="${output_probe##*/}"
    # Only the part below the deepest existing directory is handled textually, and a
    # `..` there is resolved by `mkdir` rather than by this check: the candidate would
    # read as outside the repository while the directory `mkdir` creates is inside it,
    # which is the leak this whole block exists to prevent. `pwd -P` has already
    # resolved any `..` in the part that does exist.
    if [[ "$output_component" == .. || "$output_component" == . ]]; then
        printf '%s\n' \
            "OUTPUT_DIRECTORY must not contain '$output_component' below an existing directory: $output_dir" \
            "that part of the path cannot be resolved before it is created" >&2
        exit 2
    fi
    output_suffix="/$output_component$output_suffix"
    case "$output_probe" in
        */*) output_probe="${output_probe%/*}"; [[ -n "$output_probe" ]] || output_probe=/ ;;
        *) output_probe=. ;;
    esac
done
output_candidate="$(cd -- "$output_probe" && pwd -P)$output_suffix"
if [[ "$output_candidate" == "$repo_root" || "$output_candidate" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi
"${tool_path[mkdir]}" -p -- "$output_dir"
output_dir="$(cd -- "$output_dir" && pwd -P)"
# The candidate above resolved the path that did not exist yet. Re-test the created
# directory: between the two, a component could have been replaced by a symlink
# pointing back into the repository.
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi

# Claim the directory with one atomic `mkdir`. The emptiness test above and the
# creation below do not establish ownership, so two runs aimed at the same absent or
# empty directory could both proceed and interleave gate logs, provenance files, and
# experiment output — and either could then authenticate the mixture. `mkdir` without
# `-p` fails when the name exists, so exactly one run takes it. The lock holds for the
# whole run; `rg --files` lists files, so an empty directory never enters
# `evidence.sha256`.
if ! "${tool_path[mkdir]}" -- "$output_dir/.topic18-run-lock" 2>/dev/null; then
    printf '%s\n' \
        "OUTPUT_DIRECTORY is already claimed: $output_dir/.topic18-run-lock" \
        "another run holds it, or a previous run did not remove it" >&2
    exit 2
fi
if (($# == 3)); then
    cpu="$3"
else
    allowed="$(
        "${tool_path[rg]}" --no-config -m 1 '^Cpus_allowed_list:' /proc/self/status | "${tool_path[awk]}" '{print $2}' || true
    )"
    first="${allowed%%,*}"
    cpu="${first%%-*}"
fi
# `taskset` replaces itself with a command rather than testing affinity, so this
# probe executes a program, not a shell builtin. Run a resolved and digested one:
# an unqualified `true` would run whatever `PATH` supplies, before any source
# provenance is established and without appearing in `tools.txt`. `true` cannot be
# the required tool here because it is also a Bash builtin, so `command -v` reports
# the builtin and never yields a path to record; `uname` is already required,
# already digested, and has no effect beyond its output.
if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]] \
    || ! "${tool_path[taskset]}" -c "$cpu" "${tool_path[uname]}" -m >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
    exit 2
fi

# Compare against the work-tree root rather than testing for repository
# discovery: `rev-parse --git-dir` walks upward, so an archive extracted beneath
# an unrelated checkout would otherwise adopt that ancestor's HEAD and status as
# its own source identity and skip the archive checks below.
# `core.fsmonitor` in the repository's own `.git/config` names an executable that
# `git status` runs, and `.git` is excluded from the source manifest, so that hook
# is arbitrary code with no receipt — running during the very check that decides the
# tree is clean, before `tools.txt` exists. The environment sweep cannot reach it
# because the setting is repo-local rather than an environment variable, so disable
# it per command. `-c` beats the config file for that invocation only, leaving the
# operator's own repository untouched.
# Supplying the archive variables selects archive mode outright. Detecting a checkout
# first lets an extra `.git` — a plaintext gitfile naming any repository is enough — take
# the checkout branch before `SOURCE_ARCHIVE_SHA256` or `SOURCE_MANIFEST_SHA256` is
# examined, and `scan_source_paths` excludes `.git`, so that pointer is not covered by the
# supplied manifest either. The caller has then declared archive inputs the run never
# checked while the receipt reads `git-checkout`.
if [[ -n "${SOURCE_ARCHIVE_PATH:-}${SOURCE_ARCHIVE_SHA256:-}${SOURCE_MANIFEST_SHA256:-}" ]]; then
    source_tree_mode=archive
elif [[ "$("${tool_path[git]}" -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" == "$repo_root" ]]; then
    source_tree_mode=checkout
else
    source_tree_mode=archive
fi
if [[ "$source_tree_mode" == checkout ]]; then
    # `objects/info/alternates` lets this repository borrow objects from another store, so
    # `rev-parse HEAD`, `archive`, and `ls-tree` can all read a commit and tree that exist
    # only there. `.git` is excluded from every source manifest, so neither the pointer nor
    # the borrowed objects are covered, and a worktree matching them reads as clean. The
    # `GIT_*` sweep refuses the environment form of this; the file needs its own check.
    checkout_alternates="$(
        "${tool_path[git]}" -C "$repo_root" rev-parse --git-path objects/info/alternates
    )"
    if [[ "$checkout_alternates" != /* ]]; then
        checkout_alternates="$repo_root/$checkout_alternates"
    fi
    if [[ -e "$checkout_alternates" ]]; then
        printf '%s\n' \
            "repository borrows objects from an alternate store: $checkout_alternates" \
            "the borrowed objects are outside every source manifest, so a commit that" \
            "exists only there cannot be called verified" >&2
        exit 2
    fi
    source_commit="$("${tool_path[git]}" -C "$repo_root" rev-parse HEAD)"
    # A `filter` attribute selects a `filter.<driver>.clean`, `.smudge`, or
    # `.process` command, and those commands are defined in `.git/config`, which
    # every source manifest excludes. `git archive` runs the smudge filter while
    # extracting the reference tree below, from the tree's own `.gitattributes` and
    # from `.git/info/attributes` alike. That is unrecorded code executing inside the
    # verification that attests to this source, before `tools.txt` exists. `archive`
    # has no `--no-filters`, which is why the worktree hash comparison further down
    # passes that flag and is unaffected.
    #
    # Gate on the attribute rather than on the driver definitions. A driver no
    # attribute selects never runs, and `filter.lfs.*` is present in the global
    # config of any host with git-lfs installed, so refusing on definitions would
    # refuse ordinary hosts. An attribute naming a driver with no configured command
    # is a documented pass-through, but deciding which of the two applies means
    # reading the same unrecorded `.git/config`, so refuse on selection instead. An
    # explicit `-filter` is an unset, not a selection, and stays allowed.
    #
    # Two views, because `archive` resolves attributes from the tree it archives
    # while `.git/info/attributes` and `core.attributesFile` are worktree state that
    # applies on top of it, and neither of those is covered by a manifest.
    # `check-attr` reports the effective value and runs no filter itself, as do
    # `ls-files` and `ls-tree`.
    #
    # What this does not do is freeze the attribute state: a file written between
    # this scan and the extraction below selects a driver the scan did not see. That
    # window cannot be closed from inside this process, and it is not the only
    # protection against a filter — a filter that alters content is caught by the
    # manifest comparison, which requires the extracted tree to reproduce the input
    # byte for byte. The residual is a filter that emits identical bytes and runs code
    # as a side effect.
    #
    # Probe `--source` first. It is what establishes the tree-side view, and an older
    # git rejects it inside a pipeline whose exit status the reader below does not
    # observe — which would silently skip that half of the check.
    if ! printf '' | "${tool_path[git]}" -C "$repo_root" \
        check-attr -z --stdin --source="$source_commit" filter >/dev/null 2>&1; then
        printf '%s\n' \
            "git check-attr does not support --source: ${tool_path[git]}" \
            "the tree-side attribute view cannot be established, so a smudge filter" \
            "git archive would run could not be detected here" >&2
        exit 2
    fi
    filter_selection=""
    # A path `ls-files` and `ls-tree` cannot emit: both print repository-relative
    # names, so nothing they list begins with a slash. Used below to report a failed
    # scan through the same channel as a real selection.
    attribute_scan_failed=/attribute-scan-failed
    for attribute_view in worktree "$source_commit"; do
        if [[ "$attribute_view" == worktree ]]; then
            attribute_paths=(-C "$repo_root" -c core.fsmonitor=false ls-files -z)
            attribute_query=(-C "$repo_root" check-attr -z --stdin filter)
        else
            attribute_paths=(-C "$repo_root" ls-tree -r --name-only -z "$attribute_view")
            attribute_query=(
                -C "$repo_root" check-attr -z --stdin --source="$attribute_view" filter
            )
        fi
        # `check-attr -z` emits NUL-separated triples of path, attribute, value.
        while IFS= read -r -d '' attribute_path \
            && IFS= read -r -d '' _attribute_name \
            && IFS= read -r -d '' attribute_value; do
            if [[ "$attribute_path" == "$attribute_scan_failed" ]]; then
                filter_selection+="$attribute_view: the attribute scan itself failed"$'\n'
                continue
            fi
            case "$attribute_value" in
                unspecified | unset) ;;
                *)
                    filter_selection+="$attribute_view: $attribute_path"
                    filter_selection+=" -> filter=$attribute_value"$'\n'
                    ;;
            esac
        done < <(
            # Report failure in band. `while ... done < <(pipeline)` discards the
            # substitution's exit status, so neither `set -e` nor `pipefail` can stop
            # the reader when `ls-files`, `ls-tree`, or `check-attr` fails: it would
            # see empty or truncated output, leave `filter_selection` empty, and fall
            # through to the extraction below having checked nothing. Emitting a
            # triple on failure makes a failed scan indistinguishable from a refusal.
            # `if !` disables `set -e` for the pipeline while `pipefail` still decides
            # its status, so a first stage that fails after partial output is caught.
            if ! "${tool_path[git]}" "${attribute_paths[@]}" \
                | "${tool_path[git]}" "${attribute_query[@]}"; then
                printf '%s\0filter\0scan-error\0' "$attribute_scan_failed"
            fi
        )
    done
    if [[ -n "$filter_selection" ]]; then
        printf '%s\n' \
            "attributes select a filter driver for tracked paths:" \
            "$filter_selection" \
            "the driver command lives in .git/config, which no source manifest" \
            "covers, and git archive would run it during this verification" >&2
        exit 2
    fi
    # Checkout cleanliness is decided by the manifest reproduction and the
    # `ls-tree`/`hash-object` comparison below rather than by `git status`. Those catch
    # strictly more: `status` omits ignored files while `scan_source_paths` passes
    # `-uu`, and it sees neither a sparse or skip-worktree path missing from the tree
    # nor an assume-unchanged file whose bytes no longer match its blob. They also name
    # the paths that differ instead of only reporting that something does.
    #
    # `status` is unusable here for a second reason: it executes filter policy. It
    # recurses into a populated submodule and converts that submodule's contents
    # through the submodule's own `filter.<driver>.clean`, which the scan above cannot
    # cover — `ls-files` emits a gitlink's top-level path only, so attributes inside a
    # submodule are outside every view it queries. `git archive` does not recurse into
    # a gitlink, so no check on this branch runs a filter from a submodule.
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
    # The digest, the container check, the header listing, and the extraction are
    # four separate opens of this path. A caller-writable location or a mutable
    # symlink lets them see different files, so the run could record the digest of
    # one archive while the measured snapshot came from another. Copy it once below,
    # after the scratch tree exists, and verify and read only that copy.
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

scratch_dir="$("${tool_path[mktemp]}" -d)"
# Compare physical paths: `mktemp` echoes the spelling it was given, so a
# `TMPDIR` that is a symlink into one of these trees passes a textual prefix
# test while the scratch tree is physically inside it.
scratch_dir="$(cd -- "$scratch_dir" && pwd -P)"
# Arm the removal before the guards below, which exit: `mktemp -d` has already
# created the tree, so a rejected `TMPDIR` would otherwise leave a stray `tmp.*`
# directory inside the source tree or the evidence tree that the run reports
# nothing about.
cleanup() {
    "${tool_path[rm]}" -rf -- "$scratch_dir"
}
trap cleanup EXIT
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
# Take the archive out of reach before anything reads it twice. Every later check —
# digest, container magic, header listing, extraction — runs against this private
# copy, so they cannot disagree about which bytes the run verified. The recorded
# `source_archive_path` still names what the caller supplied.
if [[ "$source_commit_verification" == verified-archive-and-manifest ]]; then
    archive_snapshot="$scratch_dir/source-archive.tar"
    "${tool_path[cp]}" -- "$SOURCE_ARCHIVE_PATH" "$archive_snapshot"
    actual_archive_sha256="$(
        "${tool_path[sha256sum]}" -- "$archive_snapshot" | "${tool_path[awk]}" '{print $1}'
    )"
    if [[ "$actual_archive_sha256" != "$SOURCE_ARCHIVE_SHA256" ]]; then
        printf 'transferred archive digest does not match SOURCE_ARCHIVE_SHA256\n' >&2
        exit 2
    fi
fi
# `-B` is a search prefix: gcc tries it, then its standard prefixes, then `PATH`. Pointing
# it at the recorded linker's own directory therefore only reorders the search, and hiding
# that file still lets another `ld` on any remaining entry link the measured binaries. Give
# `cc` a directory this run owns, holding one program named `ld`, and verify the copy
# against the digest taken before anything ran. The scratch tree is created by `mktemp -d`
# and checked to lie outside the repository and the output directory, so nothing the caller
# controls can empty it mid-run — the copy is there or the link fails.
pinned_linker_dir="$scratch_dir/pinned-linker"
"${tool_path[mkdir]}" -p -- "$pinned_linker_dir"
# `-p` because a plain copy applies the caller's umask, and gcc falls through `-B` when
# the program there is not executable — so a `umask 0111` would leave a byte-identical
# copy that cc silently declines to use. A digest cannot see a mode, so test the bit.
"${tool_path[cp]}" -p -- "${tool_path[ld]}" "$pinned_linker_dir/ld"
if [[ ! -x "$pinned_linker_dir/ld" ]]; then
    printf '%s\n' \
        "pinned linker copy is not executable: $pinned_linker_dir/ld" \
        "gcc falls through -B when the prefixed program cannot be executed" >&2
    exit 2
fi
pinned_linker_digest="$(
    "${tool_path[sha256sum]}" -- "$pinned_linker_dir/ld" | "${tool_path[awk]}" '{print $1}'
)"
if [[ "$pinned_linker_digest" != "${tool_digest[ld]}" ]]; then
    printf '%s\n' \
        "pinned linker copy does not match the recorded linker:" \
        "${tool_digest[ld]} -> $pinned_linker_digest" >&2
    exit 2
fi
experiment_work_dir="$scratch_dir/experiment-work"
# Cargo merges configuration from `$CARGO_HOME/config.toml` and every `.cargo/`
# directory above its working directory, none of which the process environment
# controls, so a caller-local `[build] rustflags` or linker override still
# reaches the gates. Point them at an empty directory instead. The workspace
# declares no external dependencies, so no registry is needed.
gate_cargo_home="$scratch_dir/cargo-home"
"${tool_path[mkdir]}" -p -- "$gate_cargo_home"
# Cargo resolves a relative target directory against its working directory,
# which is the snapshot, and the source walk excludes only `target/`. A caller
# with `CARGO_TARGET_DIR=build` would drop gate artifacts into the snapshot and
# fail the post-experiment mutation check after every measurement had been
# taken. Keep gate artifacts out of the snapshot entirely.
export CARGO_TARGET_DIR="$scratch_dir/cargo-target"
gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
# Plain `mkdir`, and both names here rather than one. `-p` accepts a path that
# already resolves to a directory, so an entry inserted after the emptiness test
# further up would be adopted instead of refused — and the run lock does not cover
# that, because it stops another copy of this script rather than an unrelated
# writer who can write the output directory. A `gates` symlink is enough on its
# own: the logs are then written through it, land outside this tree, and
# `rg --files` does not follow symlinks, so they are omitted from
# `evidence.sha256` and the run reports success while retaining none of the gate
# output it authenticates. Plain `mkdir` fails on a name that exists, so this run
# either owns both directories or stops before any gate writes into one.
#
# `experiment_dir` is created here rather than left to the driver for the same
# reason: the driver accepts an existing empty directory, and that test resolves a
# symlink as readily as `mkdir -p` does.
"${tool_path[mkdir]}" -- "$gates_dir" "$experiment_dir"
# `mkdir` establishes that the names were free; it does not bind what they refer to for
# the rest of the run. The type test before the manifest catches a substitution that
# changes the kind of object, and the path-set comparisons there catch one that changes
# which files exist — but a replacement real directory holding files under the expected
# names passes both, and `evidence.sha256` would then authenticate those files instead of
# the ones this run produced. Record device and inode now and compare before the manifest
# is written.
#
# `python3` rather than `stat`: the required-tool set is fixed above and `stat` is not in
# it, so pulling one in for a single field would widen the digested surface. `-I` for the
# same reason it is passed to every other interpreter call here.
retained_identity() {
    "${tool_path[python3]}" -I -c 'import os, sys
for path in sys.argv[1:]:
    entry = os.lstat(path)
    print(path, f"{entry.st_dev}:{entry.st_ino}")' "$@"
}
retained_identity_created="$scratch_dir/retained-identity.created"
retained_identity "$gates_dir" "$experiment_dir" >"$retained_identity_created"

# Emits NUL-separated paths relative to the caller's directory, and is the only
# definition of which files count as source. `!.git` excludes the gitdir pointer
# file a linked worktree carries in place of a directory; its contents name an
# absolute path on the running host, so it is not source.
scan_source_paths() {
    "${tool_path[rg]}" --no-config --files -uu -g '!.git/' -g '!.git' -g '!target/' -0
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
            | LC_ALL=C "${tool_path[sort]}" -z \
            | "${tool_path[xargs]}" -0 "${tool_path[sha256sum]}" --
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
    "${tool_path[mkdir]}" -p -- "$commit_tree"
    # `tar.umask` restricts the permission bits `git archive` emits, so a local
    # setting would strip modes from the reference tree itself.
    "${tool_path[git]}" -C "$input_root" -c tar.umask=0 archive --format=tar "$source_commit" \
        | "${tool_path[tar]}" --same-permissions -xf - -C "$commit_tree"
    verified_reference_tree="$commit_tree"
    verified_reference_name="$source_commit"
    manifest_source "$commit_tree" >"$output_dir/source-files.commit.sha256"
    if ! "${tool_path[cmp]}" -s \
        "$output_dir/source-files.origin.sha256" \
        "$output_dir/source-files.commit.sha256"; then
        printf 'source tree does not reproduce from %s:\n' "$source_commit" >&2
        LC_ALL=C "${tool_path[diff]}" -- \
            "$output_dir/source-files.commit.sha256" \
            "$output_dir/source-files.origin.sha256" >&2 || true
        exit 2
    fi
    # Take the commit's path set, modes, and blob identities from the object
    # database rather than from the extracted tree. `tar.umask` and archive
    # attributes shape what `git archive` emits, so a reference tree can agree
    # with a drifted worktree because the same local configuration produced both:
    # an `export-ignore` path a sparse checkout also lacks is absent from both
    # manifests, and an `export-subst` file copied back into the worktree under
    # `assume-unchanged` matches the substituted reference byte for byte. No
    # archive attribute filters `ls-tree`. Regular blobs only: a symlink's `-x`
    # follows its target and a gitlink has no worktree file here.
    tree_drift=""
    blob_paths=()
    blob_objects=()
    while IFS= read -r -d '' tree_entry; do
        tree_mode="${tree_entry%% *}"
        tree_rest="${tree_entry#* }"
        tree_object="${tree_rest%% *}"
        tree_path="${tree_rest#* }"
        case "$tree_mode" in
            100644 | 100755)
                if [[ ! -f "$input_root/$tree_path" ]]; then
                    tree_drift+="missing from the source tree: $tree_path"$'\n'
                    continue
                fi
                if [[ "$tree_mode" == 100755 ]]; then
                    [[ -x "$input_root/$tree_path" ]] \
                        || tree_drift+="missing executable bit: $tree_path"$'\n'
                else
                    [[ ! -x "$input_root/$tree_path" ]] \
                        || tree_drift+="unexpectedly executable: $tree_path"$'\n'
                fi
            blob_paths+=("$tree_path")
            blob_objects+=("$tree_object")
            ;;
        *)
            # Any other mode is unverifiable here, and silently skipping it hides
            # the entry from every check: `rg --files` omits a symlink, so a
            # `120000` path is absent from the origin, commit, before, and after
            # manifests and from the snapshot copy, and all of them agree while
            # the tree the run attests to contains a link the snapshot does not.
            # A `160000` gitlink has no worktree file to hash. Neither exists in
            # this repository, so refuse and make adding one a decision rather
            # than a silent gap in the provenance.
            tree_drift+="unsupported tree entry mode $tree_mode: $tree_path"$'\n'
            ;;
        esac
    done < <(
        "${tool_path[git]}" -C "$input_root" ls-tree -r -z \
            --format='%(objectmode) %(objectname) %(path)' "$source_commit"
    )
    # Hash the worktree files and compare object identities. One `hash-object`
    # call covers the whole tree, and it reads the files rather than the index,
    # so `assume-unchanged` cannot hide a difference the way it can from
    # `git status`.
    #
    # `--no-filters` because a `filter.<driver>.clean` command selected by
    # `.gitattributes` or `.git/info/attributes` otherwise runs during this hash,
    # and `.git` is outside the source manifest, so that is unrecorded code
    # executing inside the verification it is supposed to be subject to. Hashing
    # the bytes as they are on disk is also what this comparison means: the
    # question is whether the worktree file matches the recorded blob, not what a
    # local filter would turn it into.
    if ((${#blob_paths[@]} > 0)); then
        mapfile -t worktree_objects < <(
            cd "$input_root" \
                && "${tool_path[git]}" hash-object --no-filters -- "${blob_paths[@]}"
        )
        if ((${#worktree_objects[@]} != ${#blob_paths[@]})); then
            printf 'could not hash every tracked file in %s\n' "$input_root" >&2
            exit 2
        fi
        for blob_index in "${!blob_paths[@]}"; do
            [[ "${worktree_objects[blob_index]}" == "${blob_objects[blob_index]}" ]] \
                || tree_drift+="content differs from the commit blob: ${blob_paths[blob_index]}"$'\n'
        done
    fi
    if [[ -n "$tree_drift" ]]; then
        printf 'source tree does not match %s:\n%s' "$source_commit" "$tree_drift" >&2
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
    "${tool_path[mkdir]}" -p -- "$archive_tree"
    # Every check on this branch runs through `manifest_source` and
    # `require_matching_modes`, which walk with `rg --files`; that omits symlinks and
    # does not follow them. There is no object store here to consult the way the
    # checkout branch consults `ls-tree`, so a link inside the archive is absent
    # from the archive, origin, before, and after manifests and from the snapshot
    # copy, all of them agree, and the run still records
    # `verified-archive-and-manifest`. The tar headers are the only authority for
    # what the archive holds, so read the entry types from them and accept regular
    # files and directories alone. A tree that needs links has to extend the walker
    # and the manifest format together, which the retained `SOURCE_MANIFEST_SHA256`
    # values depend on.
    # Require an uncompressed tar. `tar` hands a compressed member to a filter
    # program — `gzip`, `xz`, `zstd` — resolved from `PATH`, and those helpers are
# not in the required-tool set, so they are neither digested nor rechecked: an
# unrecorded program would decide what the archive contains during the source
# verification that attests to it. The documented handoff writes `--format=tar`.
#
# Both directions are needed. Requiring the `ustar` magic alone is not sufficient:
# the bytes at offset 257 are read without decompressing, so a compressed stream can
# be made to carry `ustar` there — a gzip member whose stored filename field spans
# that offset does it. Refusing known compression signatures alone is not sufficient
# either, because it accepts any container it does not know. So refuse a recognised
# compression header and require the tar magic.
if ! "${tool_path[python3]}" -I -c 'import sys
COMPRESSED = (
    b"\x1f\x8b",              # gzip
    b"\x1f\x9d",              # compress
    b"\x1f\xa0",              # pack/lzh
    b"BZh",                   # bzip2
    b"\xfd7zXZ\x00",          # xz
    b"\x5d\x00\x00",          # lzma
    b"\x04\x22\x4d\x18",      # lz4
    b"\x28\xb5\x2f\xfd",      # zstd
    b"LZIP",                  # lzip
    b"\x89LZO",               # lzop
    b"PK\x03\x04",            # zip
)
with open(sys.argv[1], "rb") as archive:
    header = archive.read(512)
if any(header.startswith(magic) for magic in COMPRESSED):
    raise SystemExit(1)
raise SystemExit(0 if header[257:262] == b"ustar" else 1)' "$archive_snapshot"; then
    printf '%s\n' \
        "SOURCE_ARCHIVE_PATH must be an uncompressed tar: $SOURCE_ARCHIVE_PATH" \
        "a compressed archive is expanded by a PATH-resolved filter program that" \
        "no receipt records" >&2
    exit 2
fi
archive_entry_drift=""
while IFS= read -r archive_entry; do
    case "$archive_entry" in
        -* | d*) ;;
        *)
            archive_entry_drift+="unsupported archive entry: $archive_entry"$'\n'
            ;;
    esac
    # `--force-local` because GNU tar reads `host:path` as a remote archive over
    # `rsh`, while the digest and magic checks above and `sha256sum` all read the
    # local file of that name. Without it a name containing a colon lets `tar` list
    # and extract different bytes from the ones `source_archive_sha256` records.
done < <(LC_ALL=C "${tool_path[tar]}" --force-local -tvf "$archive_snapshot")
    if [[ -n "$archive_entry_drift" ]]; then
        printf 'archive holds entries this comparison cannot verify:\n%s' \
            "$archive_entry_drift" >&2
        exit 2
    fi
    # `--same-permissions` because tar applies the caller's umask for an ordinary
    # user, so a restrictive umask would strip modes from the reference exactly as
    # it did from an input tree extracted the same way — leaving the mode
    # comparison below to agree between two equally stripped trees.
    "${tool_path[tar]}" --force-local --same-permissions -xf "$archive_snapshot" \
        -C "$archive_tree"
    manifest_source "$archive_tree" >"$output_dir/source-files.archive.sha256"
    if ! "${tool_path[cmp]}" -s \
        "$output_dir/source-files.origin.sha256" \
        "$output_dir/source-files.archive.sha256"; then
        printf 'source tree does not reproduce from %s:\n' \
            "$SOURCE_ARCHIVE_PATH" >&2
        LC_ALL=C "${tool_path[diff]}" -- \
            "$output_dir/source-files.archive.sha256" \
            "$output_dir/source-files.origin.sha256" >&2 || true
        exit 2
    fi
    require_matching_modes "$input_root" "$archive_tree" "$SOURCE_ARCHIVE_PATH"
    verified_reference_tree="$archive_tree"
    verified_reference_name="$SOURCE_ARCHIVE_PATH"
fi
source_manifest_sha256="$(
    "${tool_path[sha256sum]}" -- "$output_dir/source-files.origin.sha256" | "${tool_path[awk]}" '{print $1}'
)"
if [[ "$source_commit_verification" == verified-archive-and-manifest ]] \
    && [[ "$source_manifest_sha256" != "$SOURCE_MANIFEST_SHA256" ]]; then
    printf 'extracted tree manifest does not match SOURCE_MANIFEST_SHA256\n' >&2
    exit 2
fi

snapshot_root="$scratch_dir/source"
"${tool_path[mkdir]}" -p -- "$snapshot_root"
(
    cd "$input_root"
    scan_source_paths \
        | "${tool_path[sort]}" -z \
        | "${tool_path[xargs]}" -0 "${tool_path[cp]}" --parents --preserve=mode --target-directory="$snapshot_root" --
)
manifest_source "$snapshot_root" >"$output_dir/source-files.before.sha256"
if ! "${tool_path[cmp]}" -s \
    "$output_dir/source-files.origin.sha256" \
    "$output_dir/source-files.before.sha256"; then
    printf 'immutable source snapshot does not match the verified input\n' >&2
    exit 1
fi
# Compare against the commit or archive reference, not the input tree. `cp
# --preserve=mode` copies whatever bit the input carries now, and the input tree stays
# mutable, so checking the snapshot against it would agree on a bit that has drifted
# from the reference provenance was established against.
require_matching_modes "$snapshot_root" "$verified_reference_tree" \
    "$verified_reference_name"
repo_root="$snapshot_root"
topic_dir="$repo_root/$topic_rel"

# Cargo merges `.cargo/config.toml` from its working directory and every parent,
# which no environment change reaches, so a configuration above the snapshot
# still decides what the gates validate. The snapshot sits under `TMPDIR`, so
# its ancestors are the caller's choice; refuse rather than validate against
# them. Pure parameter expansion so this adds no tool dependency.
config_ancestor="$repo_root"
while :; do
    # `rustfmt` searches the formatted file's directory and its ancestors for
    # `rustfmt.toml` or `.rustfmt.toml`, and Clippy searches the manifest directory
    # and then walks parents to the filesystem root for `clippy.toml` or
    # `.clippy.toml`, so the `cargo fmt` and `cargo clippy` gates would otherwise
    # run under a policy from above the snapshot that no manifest covers — the same
    # class as the Cargo configuration beside it. The snapshot itself is exempt: a
    # repository-owned formatting or lint policy is inside the verified tree and is
    # what the gate is supposed to check the repository against.
    #
    # This refusal, not `CLIPPY_CONF_DIR`, is what covers Clippy. That variable moves
    # where the search starts; it does not stop it walking parents, so pointing it at
    # the snapshot would still reach these same ancestors and close nothing.
    ancestor_configs=(
        "$config_ancestor/.cargo/config.toml"
        "$config_ancestor/.cargo/config"
    )
    if [[ "$config_ancestor" != "$repo_root" ]]; then
        ancestor_configs+=(
            "$config_ancestor/rustfmt.toml"
            "$config_ancestor/.rustfmt.toml"
            "$config_ancestor/clippy.toml"
            "$config_ancestor/.clippy.toml"
        )
    fi
    for ancestor_config in "${ancestor_configs[@]}"; do
        if [[ -e "$ancestor_config" ]]; then
            printf '%s\n' \
                "configuration above the snapshot would reach the gates: $ancestor_config" \
                "set TMPDIR to a location with no Cargo, rustfmt, or Clippy configuration above it" >&2
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
        && "${tool_path[env]}" -u RUSTUP_TOOLCHAIN "${tool_path[rustup]}" show active-toolchain \
            | "${tool_path[awk]}" '{print $1}'
)"
gate_cargo="$("${tool_path[rustup]}" which --toolchain "$gate_toolchain" cargo 2>/dev/null || true)"
if [[ ! -x "$gate_cargo" ]]; then
    printf 'rustup cannot resolve cargo for the repository toolchain %s\n' \
        "$gate_toolchain" >&2
    exit 2
fi
gate_toolchain_bin="${gate_cargo%/*}"
# The gate `PATH` restricts directories, not names: the toolchain comes first, but every
# program in the remaining directories is still reachable, so hiding a digested `cargo`,
# `rustc`, or a `cargo-<command>` helper after it is bound would change resolution rather
# than fail — and `cargo <command>` is translated into an external `cargo-<command>` found
# on `PATH`, so the helpers matter as much as `cargo` itself. Refuse when any directory
# other than the toolchain's own could answer for one of these names.
#
# Exact names, and executable regular files only: a `cargo-audit` or `rust-gdb` cannot
# satisfy any lookup the gates perform, and neither can a directory or a file without the
# execute bit, so matching by prefix would refuse runs over programs that could never
# answer. Split with parameter expansion rather than `tr`, which is not in the digested set
# and could otherwise empty the very list this guard iterates.
#
# A function, because one scan before the gates only describes the directories as they
# were at that moment. `gate_env` calls it again immediately before each gate execs, so a
# program created after the first scan is refused rather than resolved. That narrows the
# window to the gap between this check and the `execvp` that follows it; it does not close
# it, and nothing inside this process can — a name resolved by `env` is looked up after
# this shell has stopped observing. What does close it for a *bound* program is the digest
# recheck where the receipt is written, which fails the run if one changed underneath it.
require_unshadowed_gate_path() {
    gate_path_remainder="$(bound_tool_path -- \
        awk bash cc cmp cp date diff env getconf ld mkdir mktemp mv nm \
        objdump python3 rm sed sha256sum sort tar taskset uname xargs)"
    while :; do
        gate_path_directory="${gate_path_remainder%%:*}"
        gate_shadowing_programs=()
        for gate_shadowing_name in \
            cargo cargo-fmt cargo-clippy rustc rustfmt rustdoc rustup clippy-driver; do
            if [[ -f "$gate_path_directory/$gate_shadowing_name" ]] \
                && [[ -x "$gate_path_directory/$gate_shadowing_name" ]]; then
                gate_shadowing_programs+=("$gate_path_directory/$gate_shadowing_name")
            fi
        done
        if ((${#gate_shadowing_programs[@]} > 0)); then
            printf '%s\n' \
                "a gate PATH directory supplies toolchain programs: $gate_path_directory" \
                "${gate_shadowing_programs[@]}" \
                "the gates resolve cargo and its subcommand helpers through PATH, so this" \
                "directory could answer for a hidden toolchain program" >&2
            exit 2
        fi
        [[ "$gate_path_remainder" == *:* ]] || break
        gate_path_remainder="${gate_path_remainder#*:}"
    done
}
# Scan once here as well, so a host that cannot host the gates at all is refused before
# the snapshot, the receipts, and the host probe are built rather than after.
require_unshadowed_gate_path
# Bind the toolchain that runs the gates, for the same reason: the gates decide
# whether the snapshot is valid, and they execute these binaries rather than the
# proxies recorded from `PATH`. `cargo` and `rustc` are not the whole set — `cargo
# fmt`, `cargo clippy`, and `cargo doc` dispatch to separate component binaries in
# this directory, so a swapped `rustfmt`, `clippy-driver`, or `rustdoc` produces the
# retained gate logs while the `cargo` digest reads as unchanged. Components are
# installed independently, so bind each one the toolchain ships.
digest_tool gate_cargo "$gate_cargo"
# Required, not optional. `cargo fmt`, `cargo clippy`, and `cargo doc` are translated
# into external `cargo-<command>` helpers found on the gate `PATH`, so binding these
# only when present meant a component appearing between this check and its gate would
# produce that gate's log with no digest and no drift check. Every gate this script
# runs needs one of these, so absence is a refusal rather than something to skip.
for gate_component in \
    rustc rustfmt rustdoc cargo-fmt cargo-clippy clippy-driver; do
    if [[ ! -x "$gate_toolchain_bin/$gate_component" ]]; then
        printf '%s\n' \
            "toolchain $gate_toolchain lacks a component the gates need:" \
            "$gate_toolchain_bin/$gate_component" \
            "the gates run cargo fmt, test, clippy, bench, and doc, which dispatch to" \
            "these programs, so each must be present and recorded before they run" >&2
        exit 2
    fi
    digest_tool "gate_$gate_component" "$gate_toolchain_bin/$gate_component"
done

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

# `PATH` decides each name's one absolute resolution above; every call after that uses
# the saved path, so the lookup cannot drift to another directory mid-run. What `PATH`
# chose is still a choice, and resolving to a program is not resolving to the expected
# one, so name the resolved binaries and their digests here:
# a tool resolved out of a caller-writable directory is visible in this receipt
# even though no path rule can reject it, since the toolchain programs legitimately
# live under a user-owned prefix. `PATH` is recorded verbatim for the same reason.
#
# Report the digests taken before the tools ran, and refuse if any file changed
# since, which is what stops a program from forging the evidence above and then
# putting the expected bytes back in place before being recorded.
tool_drift=""
require_unchanged_tools() {
    tool_stage="$1"
    tool_drift=""
    for recorded_tool in "${!tool_path[@]}"; do
        current_tool_digest="$(
            "${tool_path[sha256sum]}" -- "${tool_path[$recorded_tool]}" | "${tool_path[awk]}" '{print $1}'
        )"
        if [[ "$current_tool_digest" != "${tool_digest[$recorded_tool]}" ]]; then
            tool_drift+="$recorded_tool ${tool_path[$recorded_tool]}"
            tool_drift+=" ${tool_digest[$recorded_tool]} -> $current_tool_digest"$'\n'
        fi
    done
    if [[ -n "$tool_drift" ]]; then
        printf 'tool changed on disk %s:\n%s' "$tool_stage" "$tool_drift" >&2
        exit 2
    fi
}
require_unchanged_tools "while establishing source provenance"
{
    printf 'path=%s\n\n' "$PATH"
    for recorded_tool in "${!tool_path[@]}"; do
        printf '%s\t%s\t%s\n' \
            "$recorded_tool" \
            "${tool_path[$recorded_tool]}" \
            "${tool_digest[$recorded_tool]}"
    done | LC_ALL=C "${tool_path[sort]}"
} >"$output_dir/tools.txt"

{
    cd "$repo_root"
    printf 'utc=%s\n' "$("${tool_path[date]}" -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_commit_verification=%s\n' "$source_commit_verification"
    printf 'source_archive_sha256=%s\n' "$recorded_archive_sha256"
    printf 'source_manifest_sha256=%s\n' "$source_manifest_sha256"
    printf 'selected_cpu=%s\n' "$cpu"
    "${tool_path[uname]}" -a
    printf 'architecture=%s\n' "$("${tool_path[uname]}" -m)"
    printf 'kernel=%s\n' "$("${tool_path[uname]}" -r)"
    printf 'online_cpus=%s\n' "$("${tool_path[getconf]}" _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$("${tool_path[getconf]}" _NPROCESSORS_CONF)"
    printf '\naffinity\n'
    "${tool_path[taskset]}" --cpu-list --pid "$$"
    printf '\nlscpu\n'
    "${tool_path[lscpu]}"
    printf '\ncpu_model_and_features\n'
    "${tool_path[rg]}" --no-config -m 128 \
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
    "${tool_path[taskset]}" -c "$cpu" "$gate_toolchain_bin/rustc" --print cfg -Ctarget-cpu=native
    printf '\nexperiment_rustc\n'
    printf 'resolved=%s\n' "$experiment_rustc"
    "$experiment_rustc" -vV
    printf '\nexperiment_native_target_cfg (taskset -c %s)\n' "$cpu"
    "${tool_path[taskset]}" -c "$cpu" "$experiment_rustc" --print cfg -Ctarget-cpu=native
    printf '\nexperiment_llvm_profdata_candidates\n'
    host="$("$experiment_rustc" -vV | "${tool_path[sed]}" -n 's/^host: //p')"
    sysroot="$("$experiment_rustc" --print sysroot)"
    printf 'rust_bundled=%s\n' "$sysroot/lib/rustlib/$host/bin/llvm-profdata"
    printf 'bound=%s\n' "${tool_path[experiment_llvm-profdata]:-not-bound}"
    printf '\nlinker_driver\n'
    printf 'resolved=%s\n' "${tool_path[cc]}"
    "${tool_path[cc]}" --version
    "${tool_path[cc]}" -dumpmachine
    printf '\nlinker\n'
    printf 'resolved=%s\n' "${tool_path[ld]}"
    "${tool_path[ld]}" --version
    printf '\npost_link_tools\n'
    for post_link_tool in llvm-bolt perf2bolt merge-fdata perf; do
        printf '%s=%s\n' "$post_link_tool" "${tool_path[$post_link_tool]:-not-bound}"
    done
    printf '\nelf_tools\n'
    "${tool_path[nm]}" --version
    "${tool_path[objdump]}" --version
    printf '\npython\n'
    "${tool_path[python3]}" --version
} >"$output_dir/host.txt" 2>&1

if [[ "$source_commit_verification" == git-checkout ]]; then
    (
    cd "$input_root"
    "${tool_path[git]}" -c core.fsmonitor=false diff --check
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
    "${tool_path[python3]}" -I -c 'import sys
source = open(sys.argv[1], "rb").read()
compile(source, sys.argv[1], "exec")
print("parsed:", sys.argv[1])' "$topic_rel/experiment/pgo_experiment.py"
    "${tool_path[bash]}" -n "$topic_rel/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

# Name the driver's environment for the same reason the gates' is named. The
# probe builds link through `cc`, which reads `LIBRARY_PATH`, `COMPILER_PATH`,
# and `GCC_EXEC_PREFIX` — a wrong `GCC_EXEC_PREFIX` fails the link outright and a
# wrong `LIBRARY_PATH` silently changes library resolution — and Python prefixes
# `PYTHONPATH` to `sys.path`, where a local `random.py` or `statistics.py` would
# replace the modules that schedule the probes and summarise the ratios. Neither
# appears in any receipt. `-I` additionally drops user site-packages, which
# survive an allowlist because `HOME` must stay for toolchain resolution.
# `RUSTUP_TOOLCHAIN` names the toolchain for the receipts and the recorded transcript.
#
# Every program this driver names is passed as a bound absolute path, because `env` and
# the driver both apply the rewritten `PATH` when they look up a command and a linked or
# custom toolchain `bin` can hold a program of the same name. `taskset` and `python3` pin
# the affinity and interpret the driver; `rustc` builds every measured binary; `cc` links
# them and `ld` is the linker it is pointed at; `nm` and `objdump` inspect them;
# `llvm-profdata` merges the training profiles; `rust-lld` and the post-link tools are
# version-probed. Each is resolved once and digested before use, so `tools.txt` names the
# programs that ran rather than the ones a later `PATH` entry could supply.
#
# So every program the driver executes is bound, and the prepended entry is left with one
# naming lookup: an optional post-link tool the wrapper did not bind is still located with
# `shutil.which`, under this `PATH`, to report whether it is present. That result is
# recorded and not run — an unbound tool is never executed — so the entry can influence an
# availability line in `post-link-tools.json` and nothing that produced a measurement.
#
# The other consumer is not a lookup by name at all: this is the `PATH` that `rustc` and
# `cc` hand to their own subprocesses, of which only `cc`'s linker child is pinned, by
# `-B`. Those two — the availability lookup above and subprocess inheritance — are what
# the rewrite is for. The Cargo gates do not run here; they ran earlier through
# `gate_env`, which prepends the repository toolchain instead.
bound_tool_env=()
for exported_tool in cc ld nm objdump llvm-bolt perf2bolt merge-fdata perf; do
    if [[ -n "${tool_path[$exported_tool]:-}" ]]; then
        bound_tool_env+=(
            "TOPIC18_TOOL_${exported_tool//-/_}=${tool_path[$exported_tool]}"
        )
    fi
done
# `rustc` and the two sysroot-bundled programs are bound under keys the driver does not
# use, and it derives all three itself. Export them under the names it looks up. Without
# this, `rustc` resolves through the rewritten `PATH` and a lookup that misses the
# toolchain copy falls through to a later entry, and `rust-lld` — optional, so its
# absence is not an error — could be a file that appeared after the binding. Each
# exported path is the one `rustup which` and the sysroot already gave, so this pins the
# toolchain the prepended directory selects rather than choosing a different one.
bound_tool_env+=("TOPIC18_TOOL_rustc=$experiment_rustc")
bound_tool_env+=("TOPIC18_LINKER_DIR=$pinned_linker_dir")
for exported_bundled in llvm-profdata rust-lld; do
    if [[ -n "${tool_path[experiment_$exported_bundled]:-}" ]]; then
        bound_tool_env+=(
            "TOPIC18_TOOL_${exported_bundled//-/_}=${tool_path[experiment_$exported_bundled]}"
        )
    fi
done
"${tool_path[env]}" -i \
    PATH="$(bound_tool_path "$experiment_toolchain_bin")" \
    HOME="$HOME" \
    LC_ALL=C \
    ${RUSTUP_HOME:+RUSTUP_HOME="$RUSTUP_HOME"} \
    RUSTUP_TOOLCHAIN="$experiment_rustup_toolchain" \
    "${bound_tool_env[@]}" \
    "${tool_path[taskset]}" -c "$cpu" "${tool_path[python3]}" -I \
    "$topic_dir/experiment/pgo_experiment.py" \
    --work-dir "$experiment_work_dir" \
    --output-dir "$experiment_dir" \
    --blocks 12 \
    --iterations 20000000 \
    --training-iterations 5000000 \
    >"$output_dir/process.log" 2>&1

# Record the driver's path set now. The wrapper does not choose these names, so the
# manifest cannot be held to a fixed list the way the gate logs below are; holding it
# to a listing taken at a different moment is what remains. A replacement between here
# and the walk changes the set and is caught; one still in place at the walk is caught
# by the identity test instead. A swap and restore that spans the driver's own writes
# is outside what this can see — the wrapper never learns what the driver meant to
# write.
experiment_paths_driver="$scratch_dir/experiment-paths.driver"
(
    cd "$experiment_dir"
    "${tool_path[rg]}" --no-config --files -uu | LC_ALL=C "${tool_path[sort]}"
) >"$experiment_paths_driver"

manifest_source "$repo_root" >"$output_dir/source-files.after.sha256"
if ! "${tool_path[cmp]}" -s \
    "$output_dir/source-files.before.sha256" \
    "$output_dir/source-files.after.sha256"; then
    printf 'source files changed during evidence collection\n' >&2
    exit 1
fi
# The manifests hash contents, so they cannot see an executable bit that a gate or the
# driver changed, and the mode comparisons all ran before those steps. Compare modes
# against the verified input again, so the retained evidence covers the modes the run
# actually finished with rather than the ones it started from.
require_matching_modes "$snapshot_root" "$verified_reference_tree" \
    "$verified_reference_name"
# The digests in `tools.txt` were taken before the provenance work and checked
# again when that receipt was written, which leaves the gates and the driver
# unguarded. Check once more here so the retained digests cover every program for
# the whole run rather than only its first half.
require_unchanged_tools "during evidence collection"

# Creating these directories empty establishes that this run made them; it does not
# hold their identity for the rest of the run. The output directory stays writable by
# whoever can write it, so `gates` or `experiment` can be removed and replaced by a
# symlink at any point after creation, and everything written afterwards lands outside
# this tree. `rg --files` does not follow symlinks, so the substitution surfaces as a
# manifest that quietly omits those trees rather than as an error. No check inside this
# process can prevent the swap — what it can do is decline to authenticate the result.
# Test the identities, then require the walk to have actually covered both.
for retained_dir in "$gates_dir" "$experiment_dir"; do
    if [[ -L "$retained_dir" ]] || [[ ! -d "$retained_dir" ]]; then
        printf '%s\n' \
            "retained output directory is not the one this run created: $retained_dir" \
            "anything written through it lies outside the tree evidence.sha256 covers" >&2
        exit 1
    fi
done
# The loop above rejects a symlink or a non-directory and gives that case a legible
# message; this compares identity, which a replacement directory of the right type
# would otherwise satisfy.
retained_identity_final="$scratch_dir/retained-identity.final"
retained_identity "$gates_dir" "$experiment_dir" >"$retained_identity_final"
if ! "${tool_path[cmp]}" -s "$retained_identity_created" "$retained_identity_final"; then
    printf 'retained output directories are not the ones this run created:\n' >&2
    LC_ALL=C "${tool_path[diff]}" -- \
        "$retained_identity_created" "$retained_identity_final" >&2 || true
    exit 1
fi

manifest_tmp="$scratch_dir/evidence.sha256"
(
    cd "$output_dir"
    "${tool_path[rg]}" --no-config --files -uu -0 . | LC_ALL=C "${tool_path[sort]}" -z | "${tool_path[xargs]}" -0 "${tool_path[sha256sum]}" --
) >"$manifest_tmp"
# These log names are this script's own, so the manifest is held to exactly that set
# rather than to "at least one entry under gates/" — a partially replaced tree leaves
# some writes inside and some outside, and any test satisfied by one surviving file
# accepts it. Both directions matter: a name missing from the manifest means that write
# landed somewhere the manifest does not cover, and an unexpected name means a gate was
# added without extending this list, which would put the new log outside this check.
expected_gate_logs=(
    cargo-bench-no-run.log
    cargo-clippy.log
    cargo-doc.log
    cargo-fmt.log
    cargo-test-doc.log
    cargo-test-lib-examples.log
    git-diff-check.log
    script-syntax.log
)
gate_logs_expected="$scratch_dir/gate-logs.expected"
gate_logs_manifest="$scratch_dir/gate-logs.manifest"
printf '%s\n' "${expected_gate_logs[@]}" | LC_ALL=C "${tool_path[sort]}" >"$gate_logs_expected"
"${tool_path[sed]}" -n 's|^[0-9a-f]\{64\}  \./gates/||p' "$manifest_tmp" \
    | LC_ALL=C "${tool_path[sort]}" >"$gate_logs_manifest"
if ! "${tool_path[cmp]}" -s "$gate_logs_expected" "$gate_logs_manifest"; then
    printf 'evidence manifest does not cover exactly the gate logs this run writes:\n' >&2
    LC_ALL=C "${tool_path[diff]}" -- "$gate_logs_expected" "$gate_logs_manifest" >&2 || true
    exit 1
fi
experiment_paths_manifest="$scratch_dir/experiment-paths.manifest"
"${tool_path[sed]}" -n 's|^[0-9a-f]\{64\}  \./experiment/||p' "$manifest_tmp" \
    | LC_ALL=C "${tool_path[sort]}" >"$experiment_paths_manifest"
if ! "${tool_path[cmp]}" -s "$experiment_paths_driver" "$experiment_paths_manifest"; then
    printf 'evidence manifest does not cover what the driver left under experiment/:\n' >&2
    LC_ALL=C "${tool_path[diff]}" -- \
        "$experiment_paths_driver" "$experiment_paths_manifest" >&2 || true
    exit 1
fi
"${tool_path[mv]}" -- "$manifest_tmp" "$output_dir/evidence.sha256"
# Remove the scratch tree here and disarm the trap rather than leaving cleanup to
# run on exit. An EXIT trap fires after the last comparison below, so the `rm` it
# runs would be the one program in the run that no digest check ever covers.
# Nothing after this point reads the scratch tree.
"${tool_path[rm]}" -rf -- "$output_dir/.topic18-run-lock"
cleanup
trap - EXIT
# The manifest itself is built by `rg`, `sort`, `xargs`, `sha256sum`, and `mv`, and
# the cleanup above runs `rm`, all after the check further up, so that check cannot
# speak for them. Repeat it once the manifest is in place and the scratch tree is
# gone: a program swapped in for this pipeline could otherwise forge
# `evidence.sha256` or leave files out of it and be restored with nothing left to
# compare against. No program runs after this comparison.
require_unchanged_tools "while writing the evidence manifest"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
