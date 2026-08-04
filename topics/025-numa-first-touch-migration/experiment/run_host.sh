#!/usr/bin/env bash
set -euo pipefail

# Build and run Topic 25 on one Linux host, retaining a sealed evidence bundle.

if (($# != 2)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY\n' "$0" >&2
    exit 2
fi
if [[ "$(uname -s)" != Linux ]]; then
    printf 'Topic 25 can run only on Linux\n' >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$(realpath -m -- "$2")"
topic_rel="topics/025-numa-first-touch-migration"
experiment_rel="$topic_rel/experiment"
experiment_dir="$repo_root/$experiment_rel"

for tool in \
    awk bash cargo cat cc cmp date getconf git gzip hostname lscpu mkdir mktemp mv \
    nm objdump python3 readelf realpath rg rustc sha256sum sort tar uname xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done
for source in \
    numa_first_touch_probe.c run_processes.py validate_receipts.py run_host.sh; do
    if [[ ! -r "$experiment_dir/$source" ]]; then
        printf 'required experiment file is unavailable: %s\n' "$source" >&2
        exit 2
    fi
done
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository\n' >&2
    exit 2
fi
if [[ -e "$output_dir" ]] && [[ -n "$(rg --files -uu "$output_dir" 2>/dev/null || true)" ]]; then
    printf 'OUTPUT_DIRECTORY must be absent or empty: %s\n' "$output_dir" >&2
    exit 2
fi
mkdir -p -- "$output_dir"

scratch_dir="$(mktemp -d)"
scratch_dir="$(cd -- "$scratch_dir" && pwd -P)"
if [[ "$scratch_dir" == "$repo_root" || "$scratch_dir" == "$repo_root"/* \
    || "$scratch_dir" == "$output_dir" || "$scratch_dir" == "$output_dir"/* \
    || "$repo_root" == "$scratch_dir"/* || "$output_dir" == "$scratch_dir"/* ]]; then
    printf 'scratch directory overlaps source or evidence directory\n' >&2
    rm -rf -- "$scratch_dir"
    exit 2
fi

scan_source_paths() {
    (
        cd "$repo_root"
        rg --files -uu -g '!.git/**' -g '!target/**' -0 | sort -z
    )
}

source_manifest() {
    (
        cd "$repo_root"
        scan_source_paths | xargs -0 sha256sum --
    )
}

seal_evidence() {
    local status="$1"
    local source_status="$2"
    printf 'exit=%s\nsource_manifest=%s\n' "$status" "$source_status" \
        >"$output_dir/run.status"
    (
        cd "$output_dir"
        rg --files -uu -g '!evidence.sha256' -0 . \
            | sort -z \
            | xargs -0 sha256sum --
    ) >"$scratch_dir/evidence.sha256"
    mv -- "$scratch_dir/evidence.sha256" "$output_dir/evidence.sha256"
}

finalize() {
    local status="$?"
    trap - EXIT
    set +e
    local source_status=not-started
    if [[ -r "$output_dir/source-files.before.sha256" ]]; then
        source_manifest >"$output_dir/source-files.after.sha256"
        if cmp -s "$output_dir/source-files.before.sha256" \
            "$output_dir/source-files.after.sha256"; then
            source_status=match
        else
            source_status=mismatch
            if ((status == 0)); then
                status=1
            fi
        fi
    fi
    printf 'utc_end=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" \
        >>"$output_dir/host.txt" 2>/dev/null || true
    seal_evidence "$status" "$source_status"
    local seal_status="$?"
    rm -rf -- "$scratch_dir"
    if ((seal_status != 0 && status == 0)); then
        status=1
    fi
    exit "$status"
}
trap finalize EXIT

if [[ "$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)" != "$repo_root" ]]; then
    printf 'REPOSITORY_ROOT must be a Git worktree root\n' >&2
    exit 2
fi
source_commit="$(git -C "$repo_root" rev-parse HEAD)"
source_tree="$(git -C "$repo_root" rev-parse HEAD^{tree})"
source_branch="$(git -C "$repo_root" branch --show-current)"
worktree_status="$(git -C "$repo_root" status --porcelain --untracked-files=all)"
if [[ -n "$worktree_status" ]]; then
    printf 'repository must be clean before evidence collection\n%s\n' "$worktree_status" >&2
    exit 2
fi

source_manifest >"$output_dir/source-files.before.sha256"
git -C "$repo_root" archive --format=tar HEAD >"$scratch_dir/source.tar"
gzip -n -9 <"$scratch_dir/source.tar" >"$output_dir/source.tar.gz"
sha256sum "$output_dir/source.tar.gz" >"$output_dir/source-archive.sha256"

swept_variables=()
while IFS= read -r variable; do
    case "$variable" in
        CC | CFLAGS | CPPFLAGS | LDFLAGS | CPATH | C_INCLUDE_PATH \
            | CPLUS_INCLUDE_PATH | COMPILER_PATH | GCC_EXEC_PREFIX \
            | LD_LIBRARY_PATH | LIBRARY_PATH | PYTHONHOME | PYTHONPATH)
            swept_variables+=("$variable")
            unset "$variable"
            ;;
    esac
done < <(compgen -e)

{
    printf 'utc_start=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'hostname=%s\n' "$(hostname -f 2>/dev/null || hostname)"
    printf 'source_commit=%s\nsource_tree=%s\nsource_branch=%s\n' \
        "$source_commit" "$source_tree" "$source_branch"
    printf 'swept_environment=%s\n' "${swept_variables[*]:-none}"
    printf 'architecture=%s\nkernel=%s\n' "$(uname -m)" "$(uname -r)"
    printf 'online_cpu_count=%s\nconfigured_cpu_count=%s\n' \
        "$(getconf _NPROCESSORS_ONLN)" "$(getconf _NPROCESSORS_CONF)"
    printf 'cpus_allowed_list=%s\nmems_allowed_list=%s\n' \
        "$(awk '/^Cpus_allowed_list:/ {print $2}' /proc/self/status)" \
        "$(awk '/^Mems_allowed_list:/ {print $2}' /proc/self/status)"
    printf 'autonuma=%s\n' "$(< /proc/sys/kernel/numa_balancing)"
    printf 'thp_enabled=%s\n' "$(< /sys/kernel/mm/transparent_hugepage/enabled)"
    printf 'thp_defrag=%s\n' "$(< /sys/kernel/mm/transparent_hugepage/defrag)"
    printf '\nuname\n'
    uname -a
    printf '\ncompiler\n'
    cc --version
    printf 'compiler_target=%s\n' "$(cc -dumpmachine)"
    printf '\ncompiler_target_options\n'
    cc -Q -march=native --help=target 2>&1 || true
    printf '\nrustc\n'
    rustc -vV
    printf '\ncargo\n'
    cargo -V
    printf '\nrust_target_cfg_native\n'
    rustc --print cfg -C target-cpu=native
    printf '\nrust_target_features\n'
    rustc --print target-features
    printf '\nlscpu\n'
    lscpu
    printf '\nproc_status_affinity\n'
    rg '^(Cpus_allowed|Cpus_allowed_list|Mems_allowed|Mems_allowed_list):' /proc/self/status
    printf '\ncgroup\n'
    cat /proc/self/cgroup
    printf '\nnuma_sysfs\n'
    shopt -s nullglob
    for node_dir in /sys/devices/system/node/node[0-9]*; do
        node_name="${node_dir##*/}"
        printf '%s cpulist=%s cpumap=%s distance=%s\n' \
            "$node_name" "$(< "$node_dir/cpulist")" "$(< "$node_dir/cpumap")" \
            "$(< "$node_dir/distance")"
        printf '%s meminfo\n' "$node_name"
        cat "$node_dir/meminfo"
    done
    shopt -u nullglob
    if command -v numactl >/dev/null 2>&1; then
        printf '\nnumactl_hardware\n'
        numactl --hardware
        printf '\nnumactl_show\n'
        numactl --show
    fi
    printf '\nvmstat_numa\n'
    rg '^(numa_|pgmigrate)' /proc/vmstat || true
} >"$output_dir/host.txt" 2>&1

{
    printf 'source_commit=%s\nsource_tree=%s\n' "$source_commit" "$source_tree"
    printf 'source_archive_sha256=%s\n' \
        "$(awk '{print $1}' "$output_dir/source-archive.sha256")"
    sha256sum \
        "$experiment_dir/numa_first_touch_probe.c" \
        "$experiment_dir/run_processes.py" \
        "$experiment_dir/validate_receipts.py" \
        "$experiment_dir/run_host.sh"
} >"$output_dir/source-identity.txt"

gates_dir="$output_dir/gates"
mkdir -p -- "$gates_dir"
(cd "$repo_root" && git diff --check) >"$gates_dir/git-diff-check.log" 2>&1
(cd "$repo_root" && cargo fmt --all -- --check) >"$gates_dir/cargo-fmt.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --lib --examples) \
    >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(cd "$repo_root" && cargo test --locked --workspace --doc) \
    >"$gates_dir/cargo-test-doc.log" 2>&1
(cd "$repo_root" && cargo clippy --locked --workspace --all-targets -- -D warnings) \
    >"$gates_dir/cargo-clippy.log" 2>&1
(cd "$repo_root" && cargo bench --locked --workspace --no-run) \
    >"$gates_dir/cargo-bench-no-run.log" 2>&1
(cd "$repo_root" && RUSTDOCFLAGS='-D warnings' cargo doc --locked --workspace --no-deps) \
    >"$gates_dir/cargo-doc.log" 2>&1
(
    cd "$repo_root"
    PYTHONPYCACHEPREFIX="$scratch_dir/pycache" python3 -m py_compile \
        "$experiment_rel/run_processes.py" \
        "$experiment_rel/validate_receipts.py"
    bash -n "$experiment_rel/run_host.sh"
) >"$gates_dir/script-syntax.log" 2>&1

build_flags=(
    -O3 -std=c11 -Wall -Wextra -Werror -Wpedantic
    -fno-lto -fno-omit-frame-pointer
)
{
    printf 'compiler=cc\n'
    printf 'flags='
    printf '%q ' "${build_flags[@]}"
    printf '\n'
} >"$output_dir/build-flags.txt"

binary="$scratch_dir/numa-first-touch-probe"
cc "${build_flags[@]}" \
    "$experiment_dir/numa_first_touch_probe.c" -o "$binary" \
    >"$output_dir/native-build.log" 2>&1
sha256sum "$binary" >"$output_dir/binary.sha256"
readelf -hSWs "$binary" >"$output_dir/binary.readelf.txt"
nm -an "$binary" >"$output_dir/binary.symbols.txt"
objdump -drwC "$binary" >"$output_dir/codegen.txt"
objdump -drwC --disassemble=topic25_first_touch "$binary" \
    >"$output_dir/codegen-first-touch.txt"
objdump -drwC --disassemble=topic25_read_mapping "$binary" \
    >"$output_dir/codegen-dependent-read.txt"
rg -q '<topic25_first_touch>:' "$output_dir/codegen-first-touch.txt"
rg -q '<topic25_read_mapping>:' "$output_dir/codegen-dependent-read.txt"
rg -n 'topic25_first_touch|topic25_read_mapping' "$output_dir/codegen.txt" \
    >"$output_dir/codegen-hook-search.txt"
gzip -9 "$output_dir/codegen.txt"

# This exact one-node-safe path is the correctness/example gate on every host.
"$binary" --control --passes 1 \
    >"$output_dir/control-smoke.jsonl" \
    2>"$output_dir/control-smoke.stderr"
test ! -s "$output_dir/control-smoke.stderr"

python3 "$experiment_dir/run_processes.py" \
    --binary "$binary" \
    --output-dir "$output_dir/experiment" \
    >"$output_dir/process.log" 2>&1

python3 "$experiment_dir/validate_receipts.py" \
    --evidence-dir "$output_dir" \
    --source-root "$repo_root" \
    >"$output_dir/validation.log" 2>&1

printf 'source_commit=%s\noutput=%s\n' "$source_commit" "$output_dir"
