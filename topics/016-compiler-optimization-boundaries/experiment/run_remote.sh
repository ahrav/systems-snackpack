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
    awk cargo cmp date dirname getconf git gzip lscpu mkdir mktemp mv nm objdump \
    python3 rg rustc sed sha256sum sort tail taskset uname xargs; do
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
    if [[ -n "$(rg --files -uu "$output_dir")" ]]; then
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
while IFS= read -r swept_variable; do
    if [[ "$swept_variable" != CARGO_HOME ]]; then
        swept_variables+=("$swept_variable")
        unset "$swept_variable"
    fi
done < <(compgen -e | rg '^(CARGO_|RUSTC|RUSTDOC|RUSTFLAGS)' || true)

cargo_home_declared="${CARGO_HOME:-$HOME/.cargo}"
if [[ "$cargo_home_declared" == /* ]]; then
    cargo_home="$cargo_home_declared"
else
    cargo_home="$repo_root/$cargo_home_declared"
fi
cargo_config_candidates=("$cargo_home/config.toml" "$cargo_home/config")
config_scan_dir="$(dirname -- "$repo_root")"
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
        printf 'external Cargo configuration is an unrecorded build input: %s\n' \
            "$cargo_config" >&2
        exit 2
    fi
done

manifest_source_files() {
    (
        cd "$repo_root"
        rg --files -uu -0 -g '!.git' -g '!target' \
            | sort -z \
            | xargs -0 sha256sum
    )
}

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
(
    cd "$output_dir"
    rg --files -uu -0 . | sort -z | xargs -0 sha256sum
) >"$evidence_manifest_tmp"
mv -- "$evidence_manifest_tmp" "$output_dir/evidence.sha256"

printf 'source_commit=%s\noutput=%s\nraw_rows=48\npairs_per_comparison=12\n' \
    "$source_commit" "$output_dir"
