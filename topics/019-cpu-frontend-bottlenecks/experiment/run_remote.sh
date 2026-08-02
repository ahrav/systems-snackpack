#!/usr/bin/env bash
set -euo pipefail

# Bash imports functions, aliases through BASH_ENV, traps, and shell options from
# the invoking environment before line 1 runs, and a DEBUG trap can re-arm any of
# them at a chosen moment -- including defining functions named builtin, declare,
# or compgen, which a backslash does not suppress because it only defeats alias
# expansion. In-shell self-verification therefore has a fixed point. Re-exec once
# through env -i with an explicit variable list, so the shell that does the real
# work starts with no imported functions, no BASH_ENV, no traps, and default
# options. The guards below still run in that shell as defence in depth.
if [[ -z "${TOPIC19_SANITIZED_SHELL:-}" ]]; then
    exec /usr/bin/env -i \
        TOPIC19_SANITIZED_SHELL=1 \
        PATH="$PATH" \
        HOME="$HOME" \
        TERM="${TERM:-dumb}" \
        TMPDIR="${TMPDIR:-/tmp}" \
        SOURCE_COMMIT="${SOURCE_COMMIT:-}" \
        SOURCE_ARCHIVE_SHA256="${SOURCE_ARCHIVE_SHA256:-}" \
        RUNTIME_HOST_ALIAS="${RUNTIME_HOST_ALIAS:-}" \
        /bin/bash "$0" "$@"
fi

# Restore a default field separator and enable pathname expansion before any
# unquoted expansion or glob below. `set -euo pipefail` clears neither, and both
# are inheritable through a startup file: an inherited IFS splits variable names
# such as LD_PRELOAD into pieces so the loader sweep unsets the wrong names, and
# an inherited noglob leaves every source-integrity glob literal so it matches
# nothing and the checks silently pass.
IFS=$' \t\n'
set +f
if [[ -o noglob ]]; then
    printf 'pathname expansion is disabled; refusing to run\n' >&2
    exit 2
fi

# Validate an exact Linux source tree and write Topic 19 evidence outside it.

# Bash imports exported functions from the environment before this script runs,
# and a function takes precedence over both PATH lookup and builtins, so an
# imported definition could redirect a tool or make the environment sweep below
# enumerate nothing while still reporting success. Reject any such definition
# before anything else, including before the alias cleanup: a backslash suppresses
# alias expansion but not function lookup, so calling shopt or unalias first would
# hand control to an imported function that could install an alias and self-unset.
#
# The enumerators themselves are shadowable, and exported functions are not
# visible to parameter expansion, so trust is established by behaviour instead of
# by assumption. Three properties are tested, because a selective replacement can
# satisfy any one of them alone: `declare -F NAME` must report a defined probe,
# the no-argument `declare -F` must list a second probe (so a `declare` that
# answers for named probes but returns nothing for the full list is caught), and
# `unset -f` must actually remove a probe. The backslash forms defeat aliases on
# the same names.
# shellcheck disable=SC2329  # invoked below, after unset -f, to test whether it survived
__integrity_probe() { return 0; }
# shellcheck disable=SC2329  # existence is asserted through declare -F, not by calling it
__integrity_probe_list() { return 0; }
if [[ -z "$(\declare -F __integrity_probe 2>/dev/null || true)" ]]; then
    printf 'declare -F does not report a defined function; refusing to run\n' >&2
    exit 2
fi
if [[ "$(\declare -F)" != *__integrity_probe_list* ]]; then
    printf 'declare -F does not list defined functions; refusing to run\n' >&2
    exit 2
fi
\unset -f __integrity_probe 2>/dev/null || true
if __integrity_probe 2>/dev/null; then
    printf 'unset -f did not remove a function; refusing to run\n' >&2
    exit 2
fi
\unset -f __integrity_probe_list 2>/dev/null || true
imported_functions="$(\declare -F)"
if [[ -n "$imported_functions" ]]; then
    printf 'refusing to run with shell functions imported from the environment:\n' >&2
    printf '%s\n' "$imported_functions" >&2
    exit 2
fi

# Bash remembers command pathnames, and `hash -p` can seed an entry that points
# `command -v` at one binary while PATH lookups in child processes -- including
# the Python analysis script -- resolve a different one. Forget them all, so the
# recorded tool paths and the tools the children run agree.
# A startup file can `unset BASH_ENV` before this check and still have left a
# trap behind, so the variable being empty proves nothing on its own. An inline
# DEBUG trap needs no function, which makes it invisible to the check above, and
# it can re-export a swept variable after the sweep has run.
#
# Clearing inherited state must succeed rather than merely be attempted: with
# `enable -n trap` or `enable -n builtin` these calls fail, and an ignored
# failure would leave the trap or the aliases in place while the environment
# report claimed otherwise. So the resets are fatal on failure and each one is
# confirmed by its postcondition. Only the code-execution traps are asserted
# empty, because an inherited ignored signal is not something this script needs
# to reject.
for __inherited_trap in DEBUG RETURN ERR EXIT HUP INT QUIT TERM; do
    \trap - "$__inherited_trap"
done
unset __inherited_trap
if [[ -n "$(\trap -p DEBUG RETURN ERR EXIT)" ]]; then
    printf 'inherited traps could not be cleared; refusing to run\n' >&2
    exit 2
fi
# A DEBUG trap runs before each command, so one could have re-enabled alias
# expansion, reinstated a function, or reset IFS or noglob immediately before it
# was removed -- which would leave every check above stale. No trap can run from
# here on, so the shell state is established again and re-verified now, and this
# is the point the later sweeps and globs actually depend on.
IFS=$' \t\n'
set +f
\builtin shopt -u expand_aliases
# failglob aborts an expansion that matches nothing, which would kill the member
# globs below on any normal checkout, and the others change what a pattern means.
\builtin shopt -u failglob nullglob dotglob nocaseglob globstar
\builtin unalias -a || true
\hash -r
# `enable -n` removes a builtin, and Bash then falls back to a PATH executable of
# the same name -- verified that a disabled `pwd` resolves through a PATH shim, so
# repo_root itself could point at a different tree, and a disabled `printf` could
# forge the recorded tool provenance. Every builtin this script depends on for
# integrity work must still be a builtin, and this runs before repo_root is
# derived or anything is recorded.
for __required_builtin in alias cd command compgen declare hash printf pwd read \
    shopt trap type unalias unset; do
    if [[ "$(\builtin type -t "$__required_builtin")" != builtin ]]; then
        printf 'shell builtin %s is unavailable; refusing to run\n' \
            "$__required_builtin" >&2
        exit 2
    fi
done
unset __required_builtin
if [[ -o noglob ]]; then
    printf 'pathname expansion is disabled; refusing to run\n' >&2
    exit 2
fi
if [[ -n "$(\alias 2>/dev/null || true)" ]]; then
    printf 'aliases could not be cleared; refusing to run\n' >&2
    exit 2
fi
# A failed enumerator must not read as an empty answer, so the listing is captured
# into a variable -- which set -e turns into a fatal error if the builtin has been
# disabled -- and then compared against exactly the probe this script defined. Any
# other entry, including one a DEBUG trap installed during the reset above, is
# refused.
# shellcheck disable=SC2329  # existence is asserted through declare -F, not by calling it
__integrity_probe_after() { return 0; }
functions_after_reset="$(\declare -F)"
if [[ "$functions_after_reset" != 'declare -f __integrity_probe_after' ]]; then
    printf 'unexpected shell functions after the trap reset; refusing to run:\n' >&2
    printf '%s\n' "$functions_after_reset" >&2
    exit 2
fi
\unset -f __integrity_probe_after
# The environment sweep below depends on `compgen -e` listing exported variables,
# and that is the enumerator a selective replacement would target, so verify it
# reports a variable this script just exported rather than trusting it.
__INTEGRITY_SENTINEL=1
export __INTEGRITY_SENTINEL
sentinel_seen=0
while IFS= read -r variable; do
    if [[ "$variable" == __INTEGRITY_SENTINEL ]]; then
        sentinel_seen=1
    fi
done < <(compgen -e)
if ((sentinel_seen != 1)); then
    printf 'compgen -e did not report an exported variable; refusing to run\n' >&2
    exit 2
fi
unset __INTEGRITY_SENTINEL
IFS=$' \t\n'
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
# The dynamic loader acts on every external command, including the ripgrep process
# the main sweep uses to find these very names, so LD_* has to go first and
# without running anything. Parameter expansion needs no external process.
swept_variables=()
for variable in ${!LD_@}; do
    swept_variables+=("$variable")
    unset "$variable"
done
# GLOBIGNORE is inert when merely inherited through the environment, because Bash
# applies its glob-ignore hook on assignment rather than on import, and the one
# route that would assign it -- BASH_ENV -- is already refused above. Clear it
# anyway, since the integrity checks below depend on globs seeing every match.
unset GLOBIGNORE
# A relative PATH component resolves against the current directory, and this
# script changes directory before the builds and gates, so a tool recorded now
# would not be the tool invoked later. An empty component means the current
# directory too, and `read -a` discards a trailing empty field, so the string is
# tested for empty components before it is split.
case ":$PATH:" in
    *::*)
        printf 'refusing to run with an empty PATH component, which means the\n' >&2
        printf 'current directory: %s\n' "$PATH" >&2
        exit 2
        ;;
esac
IFS=':' read -r -a path_entries <<<"$PATH"
for entry in "${path_entries[@]}"; do
    if [[ -z "$entry" || "$entry" != /* ]]; then
        printf 'refusing to run with a relative PATH component: %s\n' \
            "${entry:-<empty, meaning the current directory>}" >&2
        exit 2
    fi
done

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
# first Git probe, because GIT_DIR and GIT_WORK_TREE override even git -C, and
# before the tool inventory, so the match uses shell patterns rather than an
# external matcher that has not been required or hashed yet.
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
            | PYTHONPATH | PYTHONHOME | PYTHONSTARTUP)
            swept_variables+=("$variable")
            unset "$variable"
            ;;
    esac
done < <(compgen -e)
# Global and system Git configuration can assign a clean filter to tracked paths,
# and a same-size edit then leaves `git status` empty while the working tree
# differs from source_commit. Neither file is recorded source, so both are taken
# out of play for every Git probe below. The repository's own config stays in
# effect, because Git cannot operate without it.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null
# A repository-local replace ref would make cat-file return a substituted object
# while rev-parse still reports the original commit, so the blob comparison below
# would accept bytes that are not in source_commit.
export GIT_NO_REPLACE_OBJECTS=1

for tool in \
    as awk bash cargo cargo-clippy cargo-fmt cmp date gcc getconf git gzip ld ln \
    lscpu mkdir mktemp mv nm objdump perf python3 readelf rg rm rustc sed \
    sha256sum size sort stat taskset uname xargs; do
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
# in the retained evidence instead of being invisible. cargo-fmt and cargo-clippy
# are included because Cargo dispatches `cargo fmt` and `cargo clippy` to PATH
# binaries of those names, and sed because the rustup override guard depends on
# it. rustup itself is optional, and is recorded when present because that guard
# and the toolchain resolution below both rely on it.
resolved_tools=()
for tool in \
    as awk bash cargo cargo-clippy cargo-fmt cmp date gcc getconf git gzip ld ln \
    lscpu mkdir mktemp mv nm objdump perf python3 readelf rg rm rustc sed \
    sha256sum size sort stat taskset uname xargs; do
    tool_path="$(command -v "$tool")"
    # The digest comes from the hasher, but the recorded path comes from the
    # shell, so a shim cannot supply both halves of its own provenance line.
    tool_sum="$(sha256sum -- "$tool_path")"
    resolved_tools+=(
        "$(printf '%s %s %s' "$tool" "${tool_sum%% *}" "$tool_path")"
    )
done
# The GCC driver executes its own subprograms, and -print-prog-name reports bare
# names for the ones it resolves through PATH, so a shim named as or ld reaches
# the measured builds. as and ld are required and hashed above; record what the
# driver itself says it will run, resolving relative answers through PATH.
for subprogram in as ld collect2 cc1; do
    subprogram_path="$(gcc -print-prog-name="$subprogram" 2>/dev/null || true)"
    if [[ -n "$subprogram_path" && "$subprogram_path" != /* ]]; then
        subprogram_path="$(command -v "$subprogram_path" 2>/dev/null || true)"
    fi
    if [[ -n "$subprogram_path" && -f "$subprogram_path" ]]; then
        resolved_tools+=(
            "$(printf 'gcc-prog-%s %s' \
                "$subprogram" "$(sha256sum -- "$subprogram_path")")"
        )
    fi
done
if command -v rustup >/dev/null 2>&1 \
    && [[ "$(type -t rustup 2>/dev/null || true)" == file ]]; then
    rustup_path="$(command -v rustup)"
    resolved_tools+=("$(printf 'rustup %s' "$(sha256sum -- "$rustup_path")")")
    # The rustup proxies are thin, so their hashes say nothing about the toolchain
    # they dispatch to. rustup resolves the store from RUSTUP_HOME, which is swept,
    # and otherwise from HOME, which cannot be. Record the binaries that actually
    # run so a redirected store is visible in the evidence.
    # rustup resolves a toolchain from the working directory, so this must run
    # where the gates run rather than where the caller happened to stand, and it
    # must cover every binary rustup dispatches for them.
    for proxied in cargo rustc rustfmt clippy-driver rustdoc cargo-fmt cargo-clippy; do
        proxied_path="$(
            cd "$repo_root" && rustup which "$proxied" 2>/dev/null || true
        )"
        if [[ -n "$proxied_path" && -f "$proxied_path" ]]; then
            resolved_tools+=(
                "$(printf 'rustup-which-%s %s' \
                    "$proxied" "$(sha256sum -- "$proxied_path")")"
            )
        fi
    done
fi
resolved_tools+=("$(printf 'effective_rustup_home %s' "${RUSTUP_HOME:-$HOME/.rustup}")")
resolved_tools+=("$(printf 'home %s' "$HOME")")
resolved_tools+=("$(printf 'git_config_global %s' "$GIT_CONFIG_GLOBAL")")
resolved_tools+=("$(printf 'git_config_system %s' "$GIT_CONFIG_SYSTEM")")
resolved_tools+=(
    "$(printf 'git_no_replace_objects %s' "$GIT_NO_REPLACE_OBJECTS")"
)
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
# Reject a path inside the repository before creating it. mkdir -p would
# otherwise leave new directories that the root workspace's topics/* glob treats
# as members without a manifest, breaking every later Cargo invocation. A lexical
# test is not enough, because a symlinked path does not share the physical
# repo_root prefix, so the deepest existing ancestor is resolved physically and
# the remaining components are appended to it.
case "$output_dir" in
    /*) candidate_output="$output_dir" ;;
    *) candidate_output="$PWD/$output_dir" ;;
esac
# A .. component can cancel a not-yet-existing directory, so the reconstruction
# below would compare a path that mkdir -p never creates while it creates the
# canceled prefix instead. Refuse them rather than trying to normalize.
case "/$candidate_output/" in
    */../*)
        printf 'OUTPUT_DIRECTORY must not contain a .. component: %s\n' \
            "$output_dir" >&2
        exit 2
        ;;
esac
candidate_existing="$candidate_output"
candidate_tail=""
while [[ ! -d "$candidate_existing" ]]; do
    candidate_tail="${candidate_existing##*/}${candidate_tail:+/$candidate_tail}"
    candidate_existing="${candidate_existing%/*}"
    [[ -z "$candidate_existing" ]] && candidate_existing=/
done
candidate_existing="$(cd -- "$candidate_existing" && pwd -P)"
candidate_output="${candidate_existing%/}${candidate_tail:+/$candidate_tail}"
if [[ "$candidate_output" == "$repo_root" || "$candidate_output" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository: %s\n' \
        "$candidate_output" >&2
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
    # git status cannot report ignored paths at all, so an ignored Cargo.toml,
    # build.rs, or auto-discovered target stays out of the manifest while the
    # --workspace gates still load it: Cargo compiles and runs a package-root
    # build.rs automatically, and auto-discovers examples, tests, benches, and
    # src/bin targets that `cargo test --examples` and `clippy --all-targets`
    # then compile. Compare all of them against the index.
    members_root="${topic_rel%%/*}"
    hidden_members=""
    for candidate in "$repo_root/$members_root"/*/Cargo.toml \
        "$repo_root/$members_root"/*/build.rs \
        "$repo_root/$members_root"/*/src/lib.rs \
        "$repo_root/$members_root"/*/src/main.rs \
        "$repo_root/$members_root"/*/examples/*.rs \
        "$repo_root/$members_root"/*/tests/*.rs \
        "$repo_root/$members_root"/*/benches/*.rs \
        "$repo_root/$members_root"/*/src/bin/*.rs \
        "$repo_root/$members_root"/*/examples/*/main.rs \
        "$repo_root/$members_root"/*/tests/*/main.rs \
        "$repo_root/$members_root"/*/benches/*/main.rs \
        "$repo_root/$members_root"/*/src/bin/*/main.rs; do
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
    # A tracked manifest can name a target with an explicit `path`, and tracked
    # source can pull in a module with `mod` or `#[path]`, so enumerating the
    # default layouts cannot cover every compile input. Require instead that every
    # Rust source file in the tree is tracked, which holds regardless of how Cargo
    # or rustc is told to find it.
    untracked_rust=""
    while IFS= read -r candidate_rel; do
        [[ -n "$candidate_rel" ]] || continue
        if ! git -C "$repo_root" ls-files --error-unmatch -- "$candidate_rel" \
            >/dev/null 2>&1; then
            untracked_rust+=" $candidate_rel"
        fi
    done < <(
        cd "$repo_root" \
            && rg --no-config --files -uu -g '!/.git/' -g '!/target/' -g '*.rs' \
                || true
    )
    if [[ -n "$untracked_rust" ]]; then
        printf 'untracked Rust sources are present and could be compiled:%s\n' \
            "$untracked_rust" >&2
        exit 2
    fi
    # `git status` and `git diff` both apply clean filters, and repository-local
    # attributes in $GIT_DIR/info/attributes cannot be disabled by the config
    # variables exported above, so a same-size edit mapped back to the committed
    # bytes can leave both empty. Compare each tracked file's bytes against its
    # blob directly, which no filter can influence.
    if ! cmp -s \
        <(git -C "$repo_root" ls-files -z \
            | (cd "$repo_root" && LC_ALL=C sort -z | xargs -0 sha256sum --)) \
        <(git -C "$repo_root" ls-files -z \
            | LC_ALL=C sort -z \
            | while IFS= read -r -d '' blob_path; do
                # Shell-only field extraction, so the comparison does not depend
                # on an external cut that is not in the frozen inventory.
                blob_sum="$(git -C "$repo_root" cat-file blob "HEAD:$blob_path" \
                    | sha256sum --)"
                printf '%s  %s\n' "${blob_sum%% *}" "$blob_path"
            done) \
        ; then
        printf 'tracked working-tree bytes differ from their committed blobs\n' >&2
        printf 'a clean filter or index flag can hide this from git status\n' >&2
        exit 2
    fi
    # rustfmt and Clippy read configuration from the directory of the file being
    # processed and every parent, so a config nested at any depth applies -- a
    # src/rustfmt.toml changes `cargo fmt --check` for src/lib.rs. Scan the whole
    # tree, including ignored paths, and require every such file to be tracked.
    nested_configs=""
    while IFS= read -r candidate_rel; do
        [[ -n "$candidate_rel" ]] || continue
        if ! git -C "$repo_root" ls-files --error-unmatch -- "$candidate_rel" \
            >/dev/null 2>&1; then
            nested_configs+=" $candidate_rel"
        fi
    done < <(
        cd "$repo_root" \
            && rg --no-config --files -uu -g '!/.git/' -g '!/target/' \
                -g 'rustfmt.toml' -g '.rustfmt.toml' \
                -g 'clippy.toml' -g '.clippy.toml' \
                || true
    )
    if [[ -n "$nested_configs" ]]; then
        printf 'untracked rustfmt or Clippy configuration would apply to the gates:%s\n' \
            "$nested_configs" >&2
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
        "$probe_dir/clippy.toml" "$probe_dir/.clippy.toml" \
        "$probe_dir/rust-toolchain" "$probe_dir/rust-toolchain.toml"; do
        [[ -e "$candidate" ]] || continue
        # In archive mode there is no index to consult, and the source manifest is
        # an unrestricted scan of repo_root, so every file under it is recorded by
        # construction. In checkout mode only tracked files are recorded.
        if [[ "$probe_dir" == "$repo_root" ]]; then
            if [[ "$source_commit_verification" == declared-archive ]]; then
                continue
            fi
            if git -C "$repo_root" ls-files --error-unmatch -- \
                "${candidate#"$repo_root"/}" >/dev/null 2>&1; then
                continue
            fi
        fi
        unrecorded_configs+=("$candidate")
    done
    [[ "$probe_dir" == / ]] && break
    # Shell-only parent expansion, so these walks do not depend on an external
    # dirname that a PATH shim could truncate to / and stop the loop early.
    probe_dir="${probe_dir%/*}"
    [[ -z "$probe_dir" ]] && probe_dir=/
done
if ((${#unrecorded_configs[@]} > 0)); then
    printf 'unrecorded tool configuration would apply to the gates:\n' >&2
    printf '  %s\n' "${unrecorded_configs[@]}" >&2
    exit 2
fi

# A rustup directory override outranks a rust-toolchain file and is stored in
# rustup's own settings rather than the environment, so clearing RUSTUP_TOOLCHAIN
# does not remove it. When the checkout pins a toolchain, the gates are expected to
# run through rustup, so rustup must be present for that override to be checkable:
# proxy cargo/rustc honor overrides whether or not a binary named rustup is on
# PATH, and skipping the check would claim a guarantee the run cannot make.
toolchain_pin=0
if [[ -e "$repo_root/rust-toolchain.toml" || -e "$repo_root/rust-toolchain" ]]; then
    toolchain_pin=1
fi
rustup_available=0
if command -v rustup >/dev/null 2>&1 \
    && [[ "$(type -t rustup 2>/dev/null || true)" == file ]] \
    && rustup override list >/dev/null 2>&1; then
    rustup_available=1
fi
if ((toolchain_pin == 1 && rustup_available == 0)); then
    printf 'the checkout pins a toolchain but rustup is unavailable, so a\n' >&2
    printf 'directory override cannot be ruled out for the Cargo gates\n' >&2
    exit 2
fi
# Requiring rustup does not establish that the gates use it: PATH could put a
# standalone cargo ahead of the proxies, and that binary ignores the pin
# entirely. Verify the outcome instead of the mechanism -- the versions the gates
# will actually report must name the pinned channel.
if ((toolchain_pin == 1)); then
    pinned_channel="$(
        rg --no-config -m 1 '^[[:space:]]*channel[[:space:]]*=' \
            "$repo_root/rust-toolchain.toml" 2>/dev/null \
            | rg --no-config -o '"[^"]+"' | tr -d '"' || true
    )"
    if [[ -z "$pinned_channel" ]]; then
        printf 'could not read the pinned toolchain channel\n' >&2
        exit 2
    fi
    for pinned_tool in cargo rustc; do
        pinned_version="$(cd "$repo_root" && "$pinned_tool" --version)"
        if [[ "$pinned_version" != *"$pinned_channel"* ]]; then
            printf 'the %s the gates would use does not match the pinned %s\n' \
                "$pinned_tool" "$pinned_channel" >&2
            printf 'reported: %s\n' "$pinned_version" >&2
            exit 2
        fi
        resolved_tools+=(
            "$(printf 'pinned-%s-version %s' "$pinned_tool" "$pinned_version")"
        )
    done
fi
if ((rustup_available == 1)); then
    # Rows are '<path><padding><tab><toolchain>', and the padding width depends on
    # the longest path, so matching a path followed directly by a tab silently
    # misses short paths. Compare the trimmed first column instead.
    override_dirs="$(
        rustup override list 2>/dev/null \
            | rg --no-config -v '^no overrides$' \
            | sed 's/[[:space:]]*\t.*$//' || true
    )"
    probe_dir="$repo_root"
    while :; do
        while IFS= read -r override_dir; do
            [[ -n "$override_dir" ]] || continue
            if [[ "$override_dir" == "$probe_dir" ]]; then
                printf 'a rustup directory override outranks rust-toolchain.toml: %s\n' \
                    "$probe_dir" >&2
                exit 2
            fi
        done <<<"$override_dirs"
        [[ "$probe_dir" == / ]] && break
        probe_dir="${probe_dir%/*}"
        [[ -z "$probe_dir" ]] && probe_dir=/
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
# -march=native resolves from the CPU the compiler happens to run on, so on a
# host whose allowed set spans core types this must be pinned to the same CPU the
# measured processes use, or the recorded native flags and the ELFs would describe
# a different core than taskset measures.
taskset -c "$cpu" gcc -march=native -Q --help=target \
    >"$output_dir/gcc-native-target.txt" 2>&1
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
    printf '%q ' taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 \
        frontend_layout.c -o dense16
    printf '\n'
    printf 'gcc_sparse='
    printf '%q ' taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 \
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
    taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 \
        frontend_layout.c -o dense16
    taskset -c "$cpu" gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 \
        frontend_layout.c -o sparse4096
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
