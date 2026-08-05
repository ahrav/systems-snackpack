#!/usr/bin/env bash
set -euo pipefail

if [[ "${TOPIC21_SANITIZED_ENV:-}" != 1 ]]; then
    script_path="$(cd -- "$(dirname -- "$0")" && pwd -P)/${0##*/}"
    exec env -i \
        PATH="$PATH" \
        HOME="${HOME:?HOME is required}" \
        USER="${USER:-}" \
        LOGNAME="${LOGNAME:-}" \
        LC_ALL=C LANG=C TZ=UTC \
        HOST_ALIAS="${HOST_ALIAS:-unspecified}" \
        SOURCE_COMMIT="${SOURCE_COMMIT:-}" \
        TOPIC21_SANITIZED_ENV=1 \
        bash "$script_path" "$@"
fi

while IFS= read -r exported_name; do
    case "$exported_name" in
        HOME|HOST_ALIAS|LANG|LC_ALL|LOGNAME|PATH|PWD|SHLVL|SOURCE_COMMIT|TOPIC21_SANITIZED_ENV|TZ|USER)
            ;;
        *)
            printf 'unexpected exported variable after environment sanitization: %s\n' \
                "$exported_name" >&2
            exit 2
            ;;
    esac
done < <(compgen -e)

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/021-store-write-path"
topic_dir="$repo_root/$topic_rel"

for tool in \
    awk cargo chmod cmp cp date dirname env file getconf git gzip hostname lscpu \
    mkdir mktemp nm objdump python3 readelf rg rm rustc sed sha256sum sort taskset \
    uname xargs; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        printf 'required tool is unavailable: %s\n' "$tool" >&2
        exit 2
    fi
done

if [[ ! -r "$topic_dir/experiment/run_processes.py" ]] \
    || [[ ! -r "$topic_dir/benches/write_path.rs" ]]; then
    printf 'repository lacks the Topic 21 experiment sources\n' >&2
    exit 2
fi

if (($# == 3)); then
    cpu="$3"
    if ! [[ "$cpu" =~ ^(0|[1-9][0-9]*)$ ]]; then
        printf 'CPU must be a nonnegative integer\n' >&2
        exit 2
    fi
else
    allowed="$(awk '/^Cpus_allowed_list:/ {print $2; exit}' /proc/self/status)"
    first_range="${allowed%%,*}"
    cpu="${first_range%%-*}"
fi
if [[ -z "$cpu" ]] || ! taskset --cpu-list "$cpu" true >/dev/null 2>&1; then
    printf 'taskset cannot pin to CPU %s\n' "${cpu:-unknown}" >&2
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

scratch_dir="$(mktemp -d)"
scratch_dir="$(cd -- "$scratch_dir" && pwd -P)"
cleanup() {
    rm -rf -- "$scratch_dir"
}
trap cleanup EXIT
if [[ "$scratch_dir" == "$repo_root" || "$scratch_dir" == "$repo_root"/* ]]; then
    printf 'scratch directory must be outside the repository\n' >&2
    exit 2
fi

git_toplevel="$(git -C "$repo_root" rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$git_toplevel" ]] \
    || [[ "$(cd -- "$git_toplevel" && pwd -P)" != "$repo_root" ]]; then
    printf 'REPOSITORY_ROOT must be a Git worktree root\n' >&2
    exit 2
fi
source_mode=clean-git-checkout
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
if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]]; then
    printf 'Git checkout must be clean; no commit describes the measured source\n' >&2
    exit 2
fi
if ! [[ "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
    printf 'resolved source commit is not a 40-character lowercase object ID\n' >&2
    exit 2
fi

source_scan=(rg --files -uu -g '!/.git/' -g '!/target/')
scanned_paths="$scratch_dir/scanned-paths.zlist"
tracked_paths="$scratch_dir/tracked-paths.zlist"
(cd "$repo_root" && "${source_scan[@]}" -0 | sort -z) >"$scanned_paths"
git -C "$repo_root" ls-files -z | sort -z >"$tracked_paths"
if ! cmp -s "$scanned_paths" "$tracked_paths"; then
    printf 'rg source scan differs from the files tracked by SOURCE_COMMIT\n' >&2
    exit 2
fi
manifest_source() {
    (
        cd "$repo_root"
        "${source_scan[@]}" -0 | sort -z | xargs -0 sha256sum --
    )
}
manifest_source >"$output_dir/source-files.before.sha256"

# Cargo searches `.cargo` from the working directory through its ancestors.
# Reject those implicit build inputs and use a fresh CARGO_HOME. The workspace
# has no registry dependencies, so the gates and focused build can stay offline.
config_dir="$repo_root"
while :; do
    for config_name in config.toml config; do
        if [[ -f "$config_dir/.cargo/$config_name" ]]; then
            printf 'unrecorded Cargo configuration: %s\n' \
                "$config_dir/.cargo/$config_name" >&2
            exit 2
        fi
    done
    if [[ "$config_dir" == / ]]; then
        break
    fi
    config_dir="$(dirname -- "$config_dir")"
done

unset CARGO_BUILD_RUSTFLAGS CARGO_ENCODED_RUSTFLAGS CARGO_TARGET_DIR
unset RUSTC RUSTC_WRAPPER RUSTDOC RUSTDOCFLAGS RUSTFLAGS
unset LD_LIBRARY_PATH LD_PRELOAD
export CARGO_HOME="$scratch_dir/cargo-home"
export CARGO_NET_OFFLINE=true
mkdir -p -- "$CARGO_HOME"

# When cargo on PATH is a standalone binary rather than the rustup shim, the
# repository's rust-toolchain.toml pin is silently ignored and a host-default
# compiler changes the measured code generation. Fail closed on a mismatch.
if [[ -f "$repo_root/rust-toolchain.toml" ]]; then
    pinned_toolchain="$(sed -n 's/^channel = "\(.*\)"$/\1/p' "$repo_root/rust-toolchain.toml")"
    if [[ -z "$pinned_toolchain" ]]; then
        printf 'rust-toolchain.toml exists but its channel could not be parsed\n' >&2
        exit 2
    fi
    resolved_rustc="$(rustc --version | awk '{print $2}')"
    if [[ "$resolved_rustc" != "$pinned_toolchain" ]]; then
        printf 'resolved rustc %s does not match the pinned toolchain %s\n' \
            "$resolved_rustc" "$pinned_toolchain" >&2
        exit 2
    fi
fi

gates_dir="$output_dir/gates"
mkdir -p -- "$gates_dir"
gate_target="$scratch_dir/gate-target"

(cd "$repo_root" && git diff --check) >"$gates_dir/git-diff-check.log" 2>&1

(
    cd "$repo_root"
    cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    CARGO_TARGET_DIR="$gate_target" cargo test --locked --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    CARGO_TARGET_DIR="$gate_target" cargo test --locked --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    CARGO_TARGET_DIR="$gate_target" cargo clippy --locked --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    CARGO_TARGET_DIR="$gate_target" cargo bench --locked --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    RUSTDOCFLAGS='-D warnings' CARGO_TARGET_DIR="$gate_target" \
        cargo doc --locked --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1

native_rustflags='-C target-cpu=native -C codegen-units=1 -C lto=off'
focused_target="$scratch_dir/focused-target"
(
    cd "$repo_root"
    RUSTFLAGS="$native_rustflags" CARGO_TARGET_DIR="$focused_target" \
        cargo build --locked --release -p topic-021-store-write-path --bench write_path
) >"$gates_dir/focused-build.log" 2>&1

shopt -s nullglob
built_candidates=("$focused_target"/release/deps/write_path-*)
shopt -u nullglob
executables=()
for candidate in "${built_candidates[@]}"; do
    if [[ -f "$candidate" && -x "$candidate" && "$candidate" != *.d ]]; then
        executables+=("$candidate")
    fi
done
if ((${#executables[@]} != 1)); then
    printf 'expected one focused benchmark binary, found %d\n' "${#executables[@]}" >&2
    exit 1
fi

binary_dir="$output_dir/binary"
mkdir -p -- "$binary_dir"
binary="$binary_dir/write_path"
cp -- "${executables[0]}" "$binary"
chmod 0755 "$binary"
sha256sum -- "$binary" >"$binary_dir/write_path.sha256"
file -- "$binary" >"$binary_dir/write_path.file.txt"
readelf -aW "$binary" >"$binary_dir/write_path.readelf.txt"
nm -an "$binary" >"$binary_dir/write_path.symbols.txt"
for symbol in \
    topic21_temporal_store topic21_nontemporal_store \
    topic21_stlf_exact topic21_stlf_partial; do
    if ! rg -q " [Tt] ${symbol}$" "$binary_dir/write_path.symbols.txt"; then
        printf 'focused binary lacks required symbol: %s\n' "$symbol" >&2
        exit 1
    fi
    objdump -d -C --disassemble="$symbol" "$binary" \
        >"$binary_dir/write_path.$symbol.objdump.txt"
    cat -- "$binary_dir/write_path.$symbol.objdump.txt" \
        >>"$binary_dir/write_path.focused-objdump.txt"
done
objdump -d -C "$binary" | gzip -9 >"$binary_dir/write_path.objdump.txt.gz"

# Per-symbol codegen gates. Searching one concatenated disassembly would let
# an instruction in the wrong function satisfy a treatment-specific check, so
# every gate binds its pattern to a single function's disassembly, and the
# treatment-defining instructions are also asserted absent from the control.
codegen_gate() {
    local requirement="$1" pattern="$2" symbol="$3"
    local symbol_file="$binary_dir/write_path.$symbol.objdump.txt"
    case "$requirement" in
        present)
            if ! rg -qi "$pattern" "$symbol_file"; then
                printf 'codegen gate failed: %s lacks %s\n' "$symbol" "$pattern" >&2
                exit 1
            fi
            ;;
        absent)
            if rg -qi "$pattern" "$symbol_file"; then
                printf 'codegen gate failed: %s contains %s\n' "$symbol" "$pattern" >&2
                exit 1
            fi
            ;;
        *)
            printf 'internal error: unknown gate requirement %s\n' "$requirement" >&2
            exit 1
            ;;
    esac
}

codegen_review="$binary_dir/write_path.codegen-review.txt"
case "$(uname -m)" in
    x86_64)
        {
            printf 'architecture=x86_64\n'
            printf 'presence_gate=per-function: temporal VMOVAPS without VMOVNTDQ; non-temporal VMOVNTDQ then SFENCE\n'
            rg -ni '\bvmovaps\b|\bvmovntdq\b|\bsfence\b' \
                "$binary_dir/write_path.focused-objdump.txt"
            printf 'manual_geometry_gate=inspect exact [base] and partial [base+4] dependent loads below\n'
            rg -ni 'topic21_stlf_(exact|partial)|mov\s+(0x[0-9a-f]+)?\(%[a-z0-9]+\),%' \
                "$binary_dir/write_path.focused-objdump.txt" || true
        } >"$codegen_review"
        codegen_gate present '\bvmovaps\b' topic21_temporal_store
        codegen_gate absent '\bvmovntdq\b' topic21_temporal_store
        codegen_gate present '\bvmovntdq\b' topic21_nontemporal_store
        codegen_gate present '\bsfence\b' topic21_nontemporal_store
        ;;
    aarch64)
        {
            printf 'architecture=aarch64\n'
            printf 'presence_gate=per-function: temporal STP without STNP; non-temporal STNP; STLR publication in both; LDUR in both STLF kernels\n'
            rg -ni '\bstp\b|\bstnp\b|\bstlr\b' \
                "$binary_dir/write_path.focused-objdump.txt"
            printf 'manual_geometry_gate=inspect LDUR #0 exact and LDUR #4 partial below\n'
            rg -ni 'topic21_stlf_(exact|partial)|\bldur\b' \
                "$binary_dir/write_path.focused-objdump.txt"
        } >"$codegen_review"
        codegen_gate present '\bstp\b' topic21_temporal_store
        codegen_gate absent '\bstnp\b' topic21_temporal_store
        codegen_gate present '\bstnp\b' topic21_nontemporal_store
        codegen_gate present '\bstlr\b' topic21_temporal_store
        codegen_gate present '\bstlr\b' topic21_nontemporal_store
        codegen_gate present '\bldur\b' topic21_stlf_exact
        codegen_gate present '\bldur\b' topic21_stlf_partial
        ;;
    *)
        printf 'unsupported measurement architecture: %s\n' "$(uname -m)" >&2
        exit 1
        ;;
esac

"$binary" check >"$gates_dir/focused-correctness.json" 2>"$gates_dir/focused-correctness.stderr"
if [[ -s "$gates_dir/focused-correctness.stderr" ]] \
    || ! rg -q '"kind":"check".*"ok":true' "$gates_dir/focused-correctness.json"; then
    printf 'focused correctness check failed\n' >&2
    exit 1
fi

host_name="$(hostname -f 2>/dev/null || hostname)"
(
    printf 'host_alias=%s\n' "${HOST_ALIAS:-unspecified}"
    printf 'resolved_hostname=%s\n' "$host_name"
    printf 'utc=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    printf 'uname='
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    printf 'configured_cpus=%s\n' "$(getconf _NPROCESSORS_CONF)"
    printf 'selected_cpu=%s\n' "$cpu"
    printf 'process_affinity='
    taskset --cpu-list --pid "$$"
    printf '\nlscpu\n'
    lscpu
    printf '\ncpu_model_and_features\n'
    rg -m 192 \
        '^(model name|vendor_id|cpu family|model|stepping|microcode|Hardware|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features|flags)' \
        /proc/cpuinfo
    printf '\nselected_cpu_topology_and_cache\n'
    for evidence_file in \
        /sys/devices/system/cpu/cpu"$cpu"/topology/core_id \
        /sys/devices/system/cpu/cpu"$cpu"/topology/physical_package_id \
        /sys/devices/system/cpu/cpu"$cpu"/topology/thread_siblings_list \
        /sys/devices/system/cpu/cpu"$cpu"/cache/index*/level \
        /sys/devices/system/cpu/cpu"$cpu"/cache/index*/type \
        /sys/devices/system/cpu/cpu"$cpu"/cache/index*/size \
        /sys/devices/system/cpu/cpu"$cpu"/cache/index*/coherency_line_size \
        /sys/devices/system/cpu/cpu"$cpu"/cache/index*/shared_cpu_list; do
        if [[ -r "$evidence_file" ]]; then
            printf '%s=' "$evidence_file"
            awk 'NR == 1 {print; exit}' "$evidence_file"
        fi
    done
    printf '\nrust_toolchain\n'
    rustc -vV
    cargo -V
    printf '\nnative_cfg\n'
    rustc --print cfg -C target-cpu=native
    printf '\ntarget_features\n'
    rustc --print target-features
    printf '\nother_compilers\n'
    for compiler in cc gcc clang c++ g++ clang++; do
        if command -v "$compiler" >/dev/null 2>&1; then
            printf '%s_path=%s\n' "$compiler" "$(command -v "$compiler")"
            "$compiler" --version | sed -n '1,4p'
        else
            printf '%s=unavailable\n' "$compiler"
        fi
    done
    printf '\ntransparent_huge_pages\n'
    if [[ -r /sys/kernel/mm/transparent_hugepage/enabled ]]; then
        awk 'NR == 1 {print; exit}' /sys/kernel/mm/transparent_hugepage/enabled
    else
        printf 'unavailable\n'
    fi
    printf '\nperf\n'
    if command -v perf >/dev/null 2>&1; then
        perf --version
        perf list 2>/dev/null | rg -i -m 160 'rfo|store.*forward|store|writeback' || true
    else
        printf 'unavailable\n'
    fi
) >"$output_dir/host.txt" 2>&1

printf '%s\n' \
    "source_mode=$source_mode" \
    "source_commit=$source_commit" \
    "workspace_gates=sanitized environment; --locked; offline; external target directory" \
    "focused_build=--release RUSTFLAGS=$native_rustflags" \
    "focused_binary_sha256=$(awk '{print $1; exit}' "$binary_dir/write_path.sha256")" \
    "focused_affinity=taskset --cpu-list $cpu per fresh process" \
    "write_input=512 MiB" \
    "stlf_input=500000000 dependent iterations" \
    "schedule=4 A/A control blocks, then 12 primary blocks; odd ABBA, even BAAB" \
    >"$output_dir/run-manifest.txt"

results_dir="$output_dir/results"
python3 "$topic_dir/experiment/run_processes.py" \
    "$binary" "$results_dir" "$cpu" "$source_commit" \
    >"$output_dir/driver-summary.json" 2>"$output_dir/driver.stderr"
if [[ -s "$output_dir/driver.stderr" ]]; then
    printf 'driver emitted stderr\n' >&2
    exit 1
fi

manifest_source >"$output_dir/source-files.after.sha256"
if ! cmp -s "$output_dir/source-files.before.sha256" "$output_dir/source-files.after.sha256"; then
    printf 'repository source changed during the measurement run\n' >&2
    exit 1
fi
if [[ -n "$(git -C "$repo_root" status --porcelain --untracked-files=all)" ]]; then
    printf 'Git checkout became dirty during the measurement run\n' >&2
    exit 1
fi

evidence_manifest_tmp="$scratch_dir/evidence.sha256"
(
    cd "$output_dir"
    rg --files -uu -g '!evidence.sha256' -0 \
        | sort -z \
        | xargs -0 sha256sum --
) >"$evidence_manifest_tmp"
cp -- "$evidence_manifest_tmp" "$output_dir/evidence.sha256"

printf 'evidence_dir=%s\n' "$output_dir"
printf 'source_commit=%s\n' "$source_commit"
printf 'binary_sha256=%s\n' "$(awk '{print $1; exit}' "$binary_dir/write_path.sha256")"
