#!/usr/bin/env bash
set -euo pipefail

# Validates an exact source tree, runs Topic 20, and writes evidence outside it.

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/020-memory-level-parallelism"
topic_dir="$repo_root/$topic_rel"

for tool in \
    awk bash cargo cmp cp date getconf git gzip lscpu mkdir mktemp mv objdump \
    python3 realpath rg rustc sha256sum sort tar taskset uname xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done
if [[ ! -r "$topic_dir/experiment/run_processes.py" ]]; then
    printf 'repository lacks the Topic 20 experiment\n' >&2
    exit 2
fi
# realpath -m resolves without requiring existence, so containment is decided
# before anything is created and a rejected path leaves no directory behind.
output_dir="$(realpath -m -- "$output_dir")"
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi
if [[ -e "$output_dir" ]] && [[ -n "$(rg --files -uu "$output_dir" 2>/dev/null || true)" ]]; then
    printf 'OUTPUT_DIRECTORY must be absent or empty: %s\n' "$output_dir" >&2
    exit 2
fi
mkdir -p -- "$output_dir"

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

build_dir="$(mktemp -d)"
trap 'rm -rf -- "$build_dir"' EXIT

scan_source_paths() {
    rg --files -uu -g '!.git/**' -g '!target/**' -0
}
manifest_tree() {
    local root="$1"
    (
        cd "$root"
        scan_source_paths | sort -z | xargs -0 sha256sum --
    )
}
manifest_source() {
    manifest_tree "$repo_root"
}

seal_initial_failure() {
    local status="$?"
    trap - EXIT
    set +e
    printf 'exit=%s\nsource_manifest=not-started\n' "$status" \
        >"$output_dir/run.status"
    (
        cd "$output_dir"
        rg --files -uu -g '!evidence.sha256' -0 . \
            | sort -z \
            | xargs -0 sha256sum --
    ) >"$build_dir/evidence.sha256"
    mv -- "$build_dir/evidence.sha256" "$output_dir/evidence.sha256"
    rm -rf -- "$build_dir"
    exit "$status"
}
trap seal_initial_failure EXIT

if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" == "$repo_root" ]]; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
        printf 'repository must be clean\n' >&2
        exit 2
    fi
    source_verification=git-checkout
    source_trust_root=local-checkout-head
else
    if ! [[ "${SOURCE_COMMIT:-}" =~ ^[0-9a-f]{40}$ ]]; then
        printf 'SOURCE_COMMIT is required for an archive source tree\n' >&2
        exit 2
    fi
    if ! [[ "${SOURCE_ARCHIVE_SHA256:-}" =~ ^[0-9a-f]{64}$ ]]; then
        printf 'SOURCE_ARCHIVE_SHA256 is required for an archive source tree\n' >&2
        exit 2
    fi
    if [[ ! -r "${SOURCE_ARCHIVE_PATH:-}" ]]; then
        printf 'SOURCE_ARCHIVE_PATH must name the readable source archive\n' >&2
        exit 2
    fi
    actual_archive_sha256="$(sha256sum "$SOURCE_ARCHIVE_PATH" | awk '{print $1}')"
    if [[ "$actual_archive_sha256" != "$SOURCE_ARCHIVE_SHA256" ]]; then
        printf 'source archive digest mismatch\n' >&2
        exit 2
    fi
    archive_tar="$build_dir/source.tar"
    gzip -dc "$SOURCE_ARCHIVE_PATH" >"$archive_tar"
    # get-tar-commit-id reads a pax global header comment that no digest inside
    # the archive covers, so the embedded id is a claim the archive makes about
    # itself. SOURCE_ARCHIVE_SHA256 above is what actually pins these bytes.
    embedded_commit="$(git get-tar-commit-id <"$archive_tar")"
    if [[ "$embedded_commit" != "$SOURCE_COMMIT" ]]; then
        printf 'Git archive commit differs from SOURCE_COMMIT\n' >&2
        exit 2
    fi
    archive_reference="$build_dir/archive-reference"
    mkdir -p -- "$archive_reference"
    tar -xf "$archive_tar" -C "$archive_reference"
    manifest_tree "$archive_reference" >"$build_dir/archive-reference.sha256"
    manifest_source >"$build_dir/archive-source.sha256"
    if ! cmp -s "$build_dir/archive-reference.sha256" "$build_dir/archive-source.sha256"; then
        printf 'extracted source tree differs from the verified archive\n' >&2
        exit 2
    fi
    source_commit="$SOURCE_COMMIT"
    source_verification=git-archive-commit-and-tree
    source_trust_root=caller-supplied-archive-sha256
fi
if [[ -n "${SOURCE_COMMIT:-}" && "$SOURCE_COMMIT" != "$source_commit" ]]; then
    printf 'SOURCE_COMMIT does not match the source tree\n' >&2
    exit 2
fi

gates_dir="$output_dir/gates"
experiment_dir="$output_dir/experiment"
mkdir -p -- "$gates_dir"

finalize() {
    local status="$?"
    trap - EXIT
    set +e
    manifest_source >"$output_dir/source-files.after.sha256"
    if cmp -s \
        "$output_dir/source-files.before.sha256" \
        "$output_dir/source-files.after.sha256"; then
        source_manifest_status=match
    else
        source_manifest_status=mismatch
        # A gate's own code, say 101 from cargo test, says which step failed;
        # the mismatch already has its own field, so do not overwrite it.
        if ((status == 0)); then
            status=1
        fi
    fi
    printf 'utc_end=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" >>"$output_dir/host.txt"
    printf 'exit=%s\nsource_manifest=%s\n' \
        "$status" "$source_manifest_status" >"$output_dir/run.status"
    manifest_tmp="$build_dir/evidence.sha256"
    (
        cd "$output_dir"
        rg --files -uu -g '!evidence.sha256' -0 . \
            | sort -z \
            | xargs -0 sha256sum --
    ) >"$manifest_tmp"
    mv -- "$manifest_tmp" "$output_dir/evidence.sha256"
    rm -rf -- "$build_dir"
    exit "$status"
}

manifest_source >"$output_dir/source-files.before.sha256"
trap finalize EXIT

(
    cd "$repo_root"
    printf 'utc_start=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_verification=%s\n' "$source_verification"
    printf 'source_trust_root=%s\n' "$source_trust_root"
    printf 'source_archive_sha256=%s\n' "${SOURCE_ARCHIVE_SHA256:-unknown}"
    printf 'selected_cpu=%s\n' "$cpu"
    printf 'cpu_allowed_list=%s\n' \
        "$(rg -m 1 '^Cpus_allowed_list:' /proc/self/status | awk '{print $2}')"
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'page_size=%s\n' "$(getconf PAGESIZE)"
    printf 'thp=%s\n' "$(rg -m 1 '.' /sys/kernel/mm/transparent_hugepage/enabled 2>/dev/null || true)"
    printf 'perf_event_paranoid=%s\n' \
        "$(rg -m 1 '.' /proc/sys/kernel/perf_event_paranoid 2>/dev/null || true)"
    printf 'smt_active=%s\n' "$(rg -m 1 '.' /sys/devices/system/cpu/smt/active 2>/dev/null || true)"
    printf 'selected_cpu_siblings=%s\n' \
        "$(rg -m 1 '.' "/sys/devices/system/cpu/cpu${cpu}/topology/thread_siblings_list" 2>/dev/null || true)"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    # The pattern list is x86-centric plus a few AArch64 keys, and rg exits 1 on
    # no match, which would abort the run and drop the toolchain records below.
    rg -m 128 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo || true
    printf '\nrustc\n'
    rustc -vV
    printf '\ncargo\n'
    cargo -vV
    printf '\ntarget_cfg\n'
    rustc --print cfg -C target-cpu=native
) >"$output_dir/host.txt" 2>&1

if [[ "$source_verification" == git-checkout ]]; then
    (cd "$repo_root" && git diff --check) >"$gates_dir/git-diff-check.log" 2>&1
else
    printf '%s\n' \
        "status=not-applicable" \
        "reason=Git archives have no index or parent tree." \
        "source_commit=$source_commit" \
        "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
        >"$gates_dir/git-diff-check.log"
fi
(cd "$repo_root" && cargo fmt --all -- --check) >"$gates_dir/cargo-fmt.log" 2>&1
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
    cd "$repo_root"
    PYTHONPYCACHEPREFIX="$build_dir/pycache" \
        python3 -m py_compile "$topic_rel/experiment/run_processes.py"
    bash -n "$topic_rel/experiment/run_remote.sh"
) >"$gates_dir/script-syntax.log" 2>&1

target_dir="$build_dir/target"
build_flags="-C target-cpu=native -C lto=no -C codegen-units=1"
printf 'RUSTFLAGS=%s\n' "$build_flags" >"$output_dir/build-flags.txt"
(
    cd "$repo_root"
    RUSTFLAGS="$build_flags" cargo build --locked --release \
        --package memory-level-parallelism --example chain_probe \
        --target-dir "$target_dir"
) >"$output_dir/native-build.log" 2>&1
binary="$target_dir/release/examples/chain_probe"
sha256sum "$binary" >"$output_dir/binary.sha256"
objdump -drwC "$binary" >"$output_dir/codegen.txt"
rg -n 'topic20_walk_one|topic20_walk_eight' "$output_dir/codegen.txt" \
    >"$output_dir/codegen-symbol-search.txt"
objdump -drwC --disassemble=topic20_walk_one "$binary" \
    >"$output_dir/codegen-one.txt"
objdump -drwC --disassemble=topic20_walk_eight "$binary" \
    >"$output_dir/codegen-eight.txt"
rg -q '<topic20_walk_one>:' "$output_dir/codegen-one.txt"
rg -q '<topic20_walk_eight>:' "$output_dir/codegen-eight.txt"
gzip -9 "$output_dir/codegen.txt"

taskset -c "$cpu" "$binary" --lanes 1 --nodes 4096 --loads 8192 \
    >"$output_dir/smoke-one.txt"
taskset -c "$cpu" "$binary" --lanes 8 --nodes 4096 --loads 8192 \
    >"$output_dir/smoke-eight.txt"

nodes="${TOPIC20_NODES:-4194304}"
loads="${TOPIC20_LOADS:-33554432}"
python3 "$topic_dir/experiment/run_processes.py" \
    --binary "$binary" \
    --output-dir "$experiment_dir" \
    --cpu "$cpu" \
    --nodes "$nodes" \
    --loads "$loads" \
    >"$output_dir/process.log" 2>&1

record_perf_smoke() {
    local label="$1"
    local lanes="$2"
    local status reason
    set +e
    LC_ALL=C taskset -c "$cpu" perf stat \
        -e cycles,instructions,cache-misses,L1-dcache-load-misses \
        -- "$binary" --lanes "$lanes" --nodes 262144 --loads 1048576 \
        >"$output_dir/perf-${label}.stdout" \
        2>"$output_dir/perf-${label}.stderr"
    status="$?"
    set -e
    if ((status != 0)); then
        usable=no
        reason=nonzero-exit
    elif rg -qi \
        '<not supported>|<not counted>|not supported|no permission|permission denied' \
        "$output_dir/perf-${label}.stderr"; then
        usable=no
        reason=unavailable-counter
    elif ! rg -q 'cycles' "$output_dir/perf-${label}.stderr"; then
        usable=no
        reason=unrecognized-output
    else
        usable=yes
        reason=collected
    fi
    printf '%s\n' \
        "exit=$status" \
        "usable=$usable" \
        "reason=$reason" \
        "scope=smoke-only" \
        "mechanism_claim=prohibited" \
        >"$output_dir/perf-${label}.status"
}

if command -v perf >/dev/null 2>&1; then
    perf list >"$output_dir/perf-list.txt" 2>&1 || true
    record_perf_smoke one 1
    record_perf_smoke eight 8
else
    printf '%s\n' \
        "exit=127" \
        "usable=no" \
        "reason=perf-unavailable" \
        "scope=smoke-only" \
        "mechanism_claim=prohibited" \
        >"$output_dir/perf-one.status"
    cp -- "$output_dir/perf-one.status" "$output_dir/perf-eight.status"
fi

printf 'source_commit=%s\noutput=%s\ncpu=%s\n' \
    "$source_commit" "$output_dir" "$cpu"
