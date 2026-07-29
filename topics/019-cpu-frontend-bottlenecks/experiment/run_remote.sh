#!/usr/bin/env bash
set -euo pipefail

# Validate an exact Linux source tree and write Topic 19 evidence outside it.

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/019-cpu-frontend-bottlenecks"
topic_dir="$repo_root/$topic_rel"

for tool in \
    awk bash cargo cmp date gcc getconf git gzip ln lscpu mkdir mktemp mv nm \
    objdump perf python3 readelf rg rm rustc sha256sum size sort stat taskset \
    uname xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
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
    allowed="$(rg -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
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
    if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
        printf 'repository must be clean\n' >&2
        exit 2
    fi
    if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
        printf 'SOURCE_COMMIT does not match the checked-out commit\n' >&2
        exit 2
    fi
    unmanifestable="$(
        git -C "$repo_root" ls-files -s | rg -m 1 -v '^(100644|100755) ' || true
    )"
    if [[ -n "$unmanifestable" ]]; then
        printf 'tracked symbolic links or submodules are unsupported: %s\n' \
            "$unmanifestable" >&2
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

build_dir="$(mktemp -d)"
build_dir="$(cd -- "$build_dir" && pwd -P)"
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

swept_variables=()
while IFS= read -r variable; do
    swept_variables+=("$variable")
    unset "$variable"
done < <(
    compgen -e \
        | rg '^(CARGO_TARGET_DIR|CARGO_BUILD_|RUSTC$|RUSTDOC$|RUSTFLAGS$|RUSTDOCFLAGS$|LD_)' \
        || true
)
export CARGO_HOME="$build_dir/cargo-home"
export CARGO_TARGET_DIR="$build_dir/cargo-target"
mkdir -p -- "$CARGO_HOME" "$CARGO_TARGET_DIR"

manifest_source() {
    (
        cd "$repo_root"
        rg --files -uu -g '!/.git/' -g '!/target/' -0 \
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
        "$(rg -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf 'page_size=%s\n' "$(getconf PAGESIZE)"
    printf 'perf_event_paranoid=%s\n' \
        "$(rg -m 1 '^-?[0-9]+$' /proc/sys/kernel/perf_event_paranoid)"
    printf '\naffinity\n'
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo
    printf '\ngcc\n'
    gcc --version
    gcc -dumpmachine
    gcc -dumpfullversion
    printf '\nrustc\n'
    rustc -vV
    printf '\ncargo\n'
    cargo -vV
    printf '\npython\n'
    python3 --version
    printf '\ntarget_cfg\n'
    rustc --print cfg -C target-cpu=native
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
    PYTHONPYCACHEPREFIX="$build_dir/pycache" \
        python3 -m py_compile \
        "$topic_dir/experiment/generate.py" \
        "$topic_dir/experiment/frontend_experiment.py"
    bash -n "$topic_dir/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

generated_c="$frontend_dir/frontend_layout.c"
dense="$frontend_dir/dense16"
sparse="$frontend_dir/sparse4096"
aa_a="$frontend_dir/identical-a"
aa_b="$frontend_dir/identical-b"
python3 "$topic_dir/experiment/generate.py" "$generated_c"
gcc "${gcc_flags[@]}" -DFUNC_ALIGN=16 "$generated_c" -o "$dense"
gcc "${gcc_flags[@]}" -DFUNC_ALIGN=4096 "$generated_c" -o "$sparse"
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

python3 "$topic_dir/experiment/frontend_experiment.py" \
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
manifest_tmp="$(mktemp)"
(
    cd "$output_dir"
    rg --files -uu -0 . | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
