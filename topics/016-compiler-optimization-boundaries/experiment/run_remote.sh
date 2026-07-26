#!/usr/bin/env bash
set -euo pipefail

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/016-compiler-optimization-boundaries"
topic_dir="$repo_root/$topic_rel"

for tool in \
    awk cargo cmp date dirname find getconf git gzip lscpu mkdir mktemp mv nm \
    objdump python3 rg rustc sed sha256sum sort tail taskset uname wc xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done

if [[ ! -r "$topic_dir/experiment/run_processes.sh" ]] \
    || [[ ! -r "$topic_dir/experiment/summarize.py" ]]; then
    printf 'repository lacks the Topic 16 experiment scripts\n' >&2
    exit 2
fi

if (($# == 3)); then
    cpu="$3"
    if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]]; then
        printf 'CPU must be a non-negative integer\n' >&2
        exit 2
    fi
else
    allowed="$(awk '/^Cpus_allowed_list:/ {print $2; exit}' /proc/self/status)"
    first="${allowed%%,*}"
    cpu="${first%%-*}"
fi
if [[ -z "$cpu" ]] || ! taskset -c "$cpu" true >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
    exit 2
fi

if [[ -e "$output_dir" ]]; then
    if [[ ! -d "$output_dir" ]]; then
        printf 'OUTPUT_DIRECTORY exists and is not a directory: %s\n' "$output_dir" >&2
        exit 2
    fi
    # `rg --files` does not follow symbolic links, and `-uu` does not change
    # that, so a link such as `gates -> /tmp/gates` reads as an empty tree.
    # The gate-log redirections below would then write through that link while
    # the evidence manifest, which walks with the same `rg` semantics, omits
    # it. Inspect directory entries directly instead.
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
gates_dir="$output_dir/gates"
mkdir -p -- "$gates_dir"

build_dir="$(mktemp -d)"
build_dir="$(cd -- "$build_dir" && pwd -P)"
evidence_manifest_tmp=
cleanup() {
    rm -rf -- "$build_dir"
    if [[ -n "$evidence_manifest_tmp" ]]; then
        rm -f -- "$evidence_manifest_tmp"
    fi
}
trap cleanup EXIT
if [[ "$build_dir" == "$output_dir" || "$build_dir" == "$output_dir"/* ]]; then
    printf 'temporary build directory must be outside OUTPUT_DIRECTORY\n' >&2
    exit 2
fi

if git -C "$repo_root" rev-parse --git-dir >/dev/null 2>&1; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    if [[ -n "${SOURCE_COMMIT:-}" ]]; then
        declared_commit="$(
            git -C "$repo_root" rev-parse --verify --quiet "${SOURCE_COMMIT}^{commit}" || true
        )"
        if [[ "$declared_commit" != "$source_commit" ]]; then
            printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
            exit 2
        fi
    fi
    if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
        printf 'repository must be clean; no commit describes the measured source\n' >&2
        exit 2
    fi
    source_commit_verification=git-checkout
else
    if ! [[ "${SOURCE_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]]; then
        printf 'SOURCE_COMMIT is required for a non-git source tree\n' >&2
        exit 2
    fi
    source_commit="$SOURCE_COMMIT"
    source_commit_verification=declared
fi

swept_variables=()
# `LD_*` is swept alongside the Cargo and Rust variables because a dynamic
# loader override interposes arbitrary code: `LD_PRELOAD` reaches Cargo, rustc,
# the linker, and every measured process, so a preloaded allocator or clock
# shim can change both the linked artifact and the reported `steady_ns`.
# build-flags.txt names each swept variable, so an override stays visible to a
# reader instead of silently conditioning the numbers.
while IFS= read -r swept_variable; do
    if [[ "$swept_variable" != CARGO_HOME ]]; then
        swept_variables+=("$swept_variable")
        unset "$swept_variable"
    fi
done < <(compgen -e | rg '^(CARGO_|RUSTC|RUSTDOC|RUSTFLAGS|LD_)' || true)

cargo_home_declared="${CARGO_HOME:-$HOME/.cargo}"
if [[ "$cargo_home_declared" == /* ]]; then
    cargo_home="$cargo_home_declared"
else
    cargo_home="$repo_root/$cargo_home_declared"
fi
cargo_config_candidates=("$cargo_home/config.toml" "$cargo_home/config")
# Every Cargo invocation below runs with the repository root as its working
# directory, so `$repo_root/.cargo/config.toml` is consumed too. Start the walk
# at the root rather than its parent; build-flags.txt records only the flags
# this script sets, so any config file would alter the build unrecorded.
config_scan_dir="$repo_root"
while :; do
    cargo_config_candidates+=(
        "$config_scan_dir/.cargo/config.toml"
        "$config_scan_dir/.cargo/config"
    )
    if [[ "$config_scan_dir" == / ]]; then
        break
    fi
    config_scan_dir="$(dirname -- "$config_scan_dir")"
done
for cargo_config in "${cargo_config_candidates[@]}"; do
    if [[ -f "$cargo_config" ]]; then
        printf 'Cargo configuration is an unrecorded build input: %s\n' \
            "$cargo_config" >&2
        exit 2
    fi
done

# The exclusions are anchored to the repository root. A bare `!target` excludes
# every directory of that name at any depth, including a tracked input a
# package consumes through `include_bytes!`; only the workspace gates' own
# Cargo output directory at the root needs excluding, since the focused build
# writes to a separate `--target-dir` outside the repository.
source_file_scan=(rg --files -uu -g '!/.git/' -g '!/target/')
source_scan_excluded_prefixes=(.git/ target/)

manifest_source_files() {
    (
        cd "$repo_root"
        # `rg --files` emits bare relative paths, so a repository file named
        # like an option would be consumed as one. `sha256sum --help` in
        # particular prints usage and exits 0, which would put help text in
        # both manifests, satisfy the before/after `cmp`, and leave `set -e`
        # nothing to catch. Terminate options first.
        "${source_file_scan[@]}" -0 \
            | sort -z \
            | xargs -0 sha256sum --
    )
}

# `rg --files -uu` lists regular files and does not follow symbolic links,
# while Cargo does. A symlinked build input is therefore absent from both
# manifests, which then match while the binary depends on target bytes nothing
# authenticated. This applies to a `declared` source tree as well as a Git
# checkout, so it is checked against the filesystem rather than the index.
source_symlink="$(
    find "$repo_root" \
        -path "$repo_root/.git" -prune -o \
        -path "$repo_root/target" -prune -o \
        -type l -print -quit
)"
if [[ -n "$source_symlink" ]]; then
    printf 'source tree contains a symbolic link the manifest cannot record: %s\n' \
        "$source_symlink" >&2
    exit 2
fi

# The manifest hashes ignored files but the bundle retains only their hashes,
# and `git status --porcelain` reports untracked entries while staying silent
# about ignored ones. An ignored build input -- a `.git/info/exclude`d
# `.cargo/config.toml`, say -- would therefore be manifested and named part of
# a `git-checkout` source that cannot reproduce it. Require the manifested set
# and the tracked set to agree in both directions.
if [[ "$source_commit_verification" == git-checkout ]]; then
    # A submodule is a real directory, so the symlink check above cannot see
    # it, but `rg` still will not descend into one while Cargo will.
    unmanifestable_entry="$(
        git -C "$repo_root" ls-files -s | rg -m 1 -v '^(100644|100755) ' || true
    )"
    if [[ -n "$unmanifestable_entry" ]]; then
        printf 'tracked entry cannot be manifested (symbolic link or submodule): %s\n' \
            "$unmanifestable_entry" >&2
        exit 2
    fi

    # The index can be told to lie about the working tree:
    # `git update-index --assume-unchanged` leaves `git status --porcelain`
    # empty after an edit while `git ls-files` still calls the path tracked, so
    # the bundle would attribute edited bytes to HEAD. `ls-files -v` lowercases
    # the tag letter for assume-unchanged and reports `S` for skip-worktree.
    flagged_index_entry="$(
        git -C "$repo_root" ls-files -v | rg -m 1 '^[a-zS] ' || true
    )"
    if [[ -n "$flagged_index_entry" ]]; then
        printf 'index flag hides working-tree state from the cleanliness gate: %s\n' \
            "$flagged_index_entry" >&2
        exit 2
    fi

    declare -A manifested_source_files=()
    while IFS= read -r -d '' manifested_path; do
        manifested_source_files["$manifested_path"]=1
    done < <(cd "$repo_root" && "${source_file_scan[@]}" -0)

    declare -A tracked_source_files=()
    while IFS= read -r -d '' tracked_path; do
        tracked_source_files["$tracked_path"]=1
    done < <(git -C "$repo_root" ls-files -z)
    while IFS= read -r -d '' manifested_path; do
        if [[ -z "${tracked_source_files[$manifested_path]:-}" ]]; then
            printf 'manifested source input is not tracked by %s: %s\n' \
                "$source_commit" "$manifested_path" >&2
            exit 2
        fi
    done < <(cd "$repo_root" && "${source_file_scan[@]}" -0)

    # The reverse direction. Checking only that manifested paths are tracked
    # asks the scan to report its own omissions, which it cannot do: whatever
    # `rg` skips is missing from both sides of that comparison. Assert instead
    # that every tracked path outside the anchored exclusions was manifested,
    # so a future gap in the scan's coverage fails the run rather than
    # producing two matching manifests over an incomplete file set.
    for tracked_path in "${!tracked_source_files[@]}"; do
        if [[ -n "${manifested_source_files[$tracked_path]:-}" ]]; then
            continue
        fi
        excluded=0
        for excluded_prefix in "${source_scan_excluded_prefixes[@]}"; do
            if [[ "$tracked_path" == "$excluded_prefix"* ]]; then
                excluded=1
                break
            fi
        done
        if ((!excluded)); then
            printf 'tracked source input is missing from the manifest: %s\n' \
                "$tracked_path" >&2
            exit 2
        fi
    done
fi

manifest_source_files >"$output_dir/source-files.before.sha256"
native_rustflags="-C target-cpu=native -C codegen-units=1 -C lto=off"
printf '%s\n' \
    "source_commit=$source_commit" \
    "source_commit_verification=$source_commit_verification" \
    "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
    "workspace_gates=compiler defaults with --locked" \
    "focused_build=--release RUSTFLAGS=$native_rustflags" \
    "focused_affinity=taskset -c $cpu" \
    "focused_workload=binary defaults; TOPIC16_ELEMENTS and TOPIC16_ROUNDS unset" \
    "swept_build_environment=${swept_variables[*]:-none}" \
    >"$output_dir/build-flags.txt"

host_name="$(uname -n)"
(
    cd "$repo_root"
    printf 'utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf 'affinity='
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo
    printf '\nrustc_verbose\n'
    rustc -vV
    printf '\ncargo_version\n'
    cargo -V
    printf '\nenabled_native_cfg\n'
    rustc --print cfg -C target-cpu=native
    printf '\nsupported_target_features\n'
    rustc --print target-features
    printf '\ncompilers\n'
    for compiler in cc gcc clang c++ g++ clang++; do
        if command -v "$compiler" >/dev/null 2>&1; then
            printf '%s_path=%s\n' "$compiler" "$(command -v "$compiler")"
            "$compiler" --version | sed -n '1,4p'
        else
            printf '%s=unavailable\n' "$compiler"
        fi
    done
) 2>&1 | sed "s/${host_name}/redacted-host/g" >"$output_dir/host.txt"

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
    cd "$repo_root"
    RUSTFLAGS="$native_rustflags" cargo build \
        --locked \
        --release \
        --target-dir "$build_dir" \
        -p compiler-optimization-boundaries \
        --example boundary_probe
) >"$output_dir/native-build.log" 2>&1

binary="$build_dir/release/examples/boundary_probe"
if [[ ! -x "$binary" ]]; then
    printf 'focused build did not produce %s\n' "$binary" >&2
    exit 1
fi
(cd -- "$(dirname -- "$binary")" && sha256sum "$(basename -- "$binary")") \
    >"$output_dir/boundary_probe.sha256"

# Evidence runs use the binary's recorded defaults. The process runner accepts
# these variables only to make a short local smoke run practical.
unset TOPIC16_ELEMENTS TOPIC16_ROUNDS
: >"$output_dir/correctness.log"
for mode in local imported opaque; do
    taskset -c "$cpu" "$binary" "$mode" >>"$output_dir/correctness.log"
done
python3 - "$output_dir/correctness.log" <<'PY'
import sys

expected_modes = ["local", "imported", "opaque"]
lines = open(sys.argv[1], encoding="utf-8").read().splitlines()
if len(lines) != len(expected_modes):
    raise SystemExit("correctness probe did not emit exactly three rows")
fixtures = set()
for expected, line in zip(expected_modes, lines):
    fields = dict(token.split("=", 1) for token in line.split())
    if set(fields) != {"mode", "elements", "rounds", "checksum", "steady_ns"}:
        raise SystemExit(f"{expected}: correctness schema mismatch")
    if fields["mode"] != expected:
        raise SystemExit(f"{expected}: process reported mode {fields['mode']}")
    fixtures.add((fields["elements"], fields["rounds"], fields["checksum"]))
if len(fixtures) != 1:
    raise SystemExit("local, imported, and opaque paths returned different checksums")
PY

"$topic_dir/experiment/run_processes.sh" \
    "$binary" \
    "$output_dir/raw.csv" \
    "$output_dir/summary.csv" \
    "$cpu" \
    >"$output_dir/process.log" 2>&1
resolved_affinity="$(sed -n 's/^affinity=//p' "$output_dir/process.log" | tail -1)"
if [[ "$resolved_affinity" != "taskset -c $cpu" ]]; then
    printf 'runner reported unexpected affinity: %s\n' "${resolved_affinity:-missing}" >&2
    exit 1
fi
printf 'focused_affinity_actual=%s\n' "$resolved_affinity" \
    >"$output_dir/affinity-resolved.txt"

(cd -- "$(dirname -- "$binary")" && nm -n -C "$(basename -- "$binary")") \
    >"$output_dir/boundary_probe.symbols.txt"
(cd -- "$(dirname -- "$binary")" && objdump -d -C "$(basename -- "$binary")") \
    >"$output_dir/codegen-full.txt"
for symbol in topic16_opaque_mix run_local run_imported run_opaque; do
    if ! rg -F "$symbol" "$output_dir/boundary_probe.symbols.txt" >/dev/null; then
        printf 'linked image lacks required symbol: %s\n' "$symbol" >&2
        exit 1
    fi
done
rg ' (topic16_opaque_mix|run_local|run_imported|run_opaque)$' \
    "$output_dir/boundary_probe.symbols.txt" \
    >"$output_dir/boundary-symbol-addresses.txt"
(
    cd -- "$(dirname -- "$binary")"
    for symbol in topic16_opaque_mix run_local run_imported run_opaque; do
        address="$(
            awk -v target="$symbol" '$NF == target { print $1; exit }' \
                "$output_dir/boundary-symbol-addresses.txt"
        )"
        if ! [[ "$address" =~ ^[0-9a-fA-F]+$ ]]; then
            printf 'cannot resolve linked address for %s\n' "$symbol" >&2
            exit 1
        fi
        stop_address="$(printf '%x' "$((16#$address + 1024))")"
        printf '\n===== %s address=0x%s =====\n' "$symbol" "$address"
        objdump -d -C \
            --start-address="0x$address" \
            --stop-address="0x$stop_address" \
            "$(basename -- "$binary")"
    done
) >"$output_dir/codegen-boundaries.txt"
gzip -9 "$output_dir/codegen-full.txt"

manifest_source_files >"$output_dir/source-files.after.sha256"
if ! cmp -s \
    "$output_dir/source-files.before.sha256" \
    "$output_dir/source-files.after.sha256"; then
    printf 'source files changed during evidence collection\n' >&2
    exit 1
fi

evidence_manifest_tmp="$(mktemp)"
# The walk below shares `rg`'s no-follow semantics, so a symbolic link anywhere
# in the bundle would be hashed nowhere while still resolving to bytes a reader
# would treat as evidence.
if [[ -n "$(find "$output_dir" -type l -print -quit)" ]]; then
    printf 'evidence bundle contains a symbolic link; the manifest would omit it\n' >&2
    exit 1
fi
(
    cd "$output_dir"
    rg --files -uu -0 . | sort -z | xargs -0 sha256sum --
) >"$evidence_manifest_tmp"
mv -- "$evidence_manifest_tmp" "$output_dir/evidence.sha256"

raw_rows=$(($(wc -l <"$output_dir/raw.csv") - 1))
pairs_per_comparison="$(
    sed -n 's/^pairs_per_comparison=//p' "$output_dir/process.log" | tail -1
)"
if ! [[ "$pairs_per_comparison" =~ ^[1-9][0-9]*$ ]]; then
    printf 'runner did not report pairs_per_comparison\n' >&2
    exit 1
fi
comparisons_measured="$(
    awk -F, 'NR > 1 { print $1 }' "$output_dir/raw.csv" | sort -u | wc -l
)"
# The AB/BA design measures both modes once per pair, so each pair contributes
# two rows. Deriving the total from the runner's own report keeps this summary
# from drifting when the pair count changes.
expected_rows=$((comparisons_measured * pairs_per_comparison * 2))
if ((raw_rows != expected_rows)); then
    printf 'raw record holds %d rows; %d comparisons x %d pairs x 2 implies %d\n' \
        "$raw_rows" "$comparisons_measured" "$pairs_per_comparison" \
        "$expected_rows" >&2
    exit 1
fi

printf 'source_commit=%s\noutput=%s\nraw_rows=%d\npairs_per_comparison=%d\n' \
    "$source_commit" "$output_dir" "$raw_rows" "$pairs_per_comparison"
