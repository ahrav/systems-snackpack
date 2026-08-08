#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 5 ]]; then
    echo "usage: run_host.sh REPOSITORY OUTPUT HOST_LABEL SOURCE_COMMIT SOURCE_ARCHIVE_SHA256" >&2
    exit 2
fi

repository=$(realpath "$1")
output=$(realpath -m "$2")
host_label=$3
source_commit=$4
source_archive_sha256=$5
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)

if [[ $(uname -s) != Linux ]]; then
    echo "run_host.sh requires Linux" >&2
    exit 2
fi

if [[ ! -d "$repository/topics/029-distributed-time-ordering" ]]; then
    echo "Topic 29 source is absent from repository: $repository" >&2
    exit 2
fi
if [[ -e "$output" ]]; then
    echo "output already exists: $output" >&2
    exit 2
fi
case "$output/" in
    "$repository/"*)
        echo "output must be outside the source tree" >&2
        exit 2
        ;;
esac
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "source commit must be 40 lowercase hexadecimal characters" >&2
    exit 2
fi
if [[ ! $source_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
    echo "source archive SHA-256 must be 64 lowercase hexadecimal characters" >&2
    exit 2
fi

mkdir -p "$output/gates"
topic="$repository/topics/029-distributed-time-ordering"

controlled_environment=(
    CARGO_BUILD_RUSTFLAGS
    CARGO_ENCODED_RUSTFLAGS
    CARGO_TARGET_DIR
    RUSTC_WRAPPER
    RUSTC_WORKSPACE_WRAPPER
    RUSTFLAGS
    RUSTDOCFLAGS
)
for variable in "${controlled_environment[@]}"; do
    if [[ -v $variable ]]; then
        printf '%s=%q\n' "$variable" "${!variable}"
    else
        printf '%s=<unset>\n' "$variable"
    fi
    unset "$variable"
done >"$output/environment.before.txt"

{
    echo "host_label=$host_label"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
} >"$output/source_identity.txt"

{
    echo "host_label=$host_label"
    hostname -f
    uname -a
    uname -m
    uname -r
    getconf _NPROCESSORS_ONLN
    lscpu
    rustc -vV
    cargo -V
    cc --version
    objdump --version
    rustc --print cfg
    rustc -C target-cpu=native --print cfg
} >"$output/host.txt" 2>&1

{
    echo "generic: RUSTFLAGS unset"
    echo "native: RUSTFLAGS=-C target-cpu=native"
    echo "workspace gates: RUSTFLAGS unset"
} >"$output/build-flags.txt"

source_manifest() {
    (
        cd "$repository"
        rg --files Cargo.toml Cargo.lock topics/029-distributed-time-ordering \
            | sort \
            | xargs sha256sum
    )
}

source_manifest >"$output/source-files.before.sha256"

run_gate() {
    local name=$1
    shift
    (
        cd "$repository"
        "$@"
    ) >"$output/gates/$name.log" 2>&1
}

run_gate cargo-fmt cargo fmt --all -- --check

unset RUSTFLAGS || true
run_gate cargo-test-package-generic cargo test --locked \
    --package distributed-time-ordering
run_gate cargo-build-package-generic cargo build --locked --release \
    --package distributed-time-ordering --bin ordering-probe

generic_binary="$repository/target/release/ordering-probe"
cp "$generic_binary" "$output/ordering-probe.generic"
sha256sum "$output/ordering-probe.generic" >"$output/binary.generic.sha256"
python3 "$topic/experiment/run_processes.py" \
    "$output/ordering-probe.generic" \
    "$output/experiment-generic" >"$output/process-runner.generic.log" 2>&1
python3 "$topic/experiment/validate_receipts.py" \
    "$output/experiment-generic" >"$output/validation.generic.log" 2>&1
generic_recorded_sha256=$(awk 'NR == 1 { print $1 }' \
    "$output/experiment-generic/binary.sha256")
generic_actual_sha256=$(sha256sum "$output/ordering-probe.generic" \
    | awk '{ print $1 }')
[[ $generic_recorded_sha256 == "$generic_actual_sha256" ]]

export RUSTFLAGS="-C target-cpu=native"
run_gate cargo-test-package-native cargo test --locked \
    --package distributed-time-ordering
run_gate cargo-build-package-native cargo build --locked --release \
    --package distributed-time-ordering --bin ordering-probe

binary="$repository/target/release/ordering-probe"
cp "$binary" "$output/ordering-probe.native"
sha256sum "$output/ordering-probe.native" >"$output/binary.native.sha256"
nm -n "$binary" >"$output/binary.symbols.txt"
for symbol in \
    topic29_lww_choice \
    topic29_lamport_receive \
    topic29_vector_relation \
    topic29_hlc_receive
do
    rg -q "[[:space:]][Tt][[:space:]]${symbol}$" \
        "$output/binary.symbols.txt"
    objdump -d --no-show-raw-insn --disassemble="$symbol" "$binary"
done >"$output/codegen.txt" 2>&1
for symbol in \
    topic29_lww_choice \
    topic29_lamport_receive \
    topic29_vector_relation \
    topic29_hlc_receive
do
    rg -q "<${symbol}>:" "$output/codegen.txt"
done

python3 "$topic/experiment/run_processes.py" "$binary" \
    "$output/experiment-native" >"$output/process-runner.native.log" 2>&1
python3 "$topic/experiment/validate_receipts.py" \
    "$output/experiment-native" >"$output/validation.native.log" 2>&1
native_recorded_sha256=$(awk 'NR == 1 { print $1 }' \
    "$output/experiment-native/binary.sha256")
native_actual_sha256=$(sha256sum "$output/ordering-probe.native" \
    | awk '{ print $1 }')
[[ $native_recorded_sha256 == "$native_actual_sha256" ]]

unset RUSTFLAGS
run_gate cargo-test-lib-examples cargo test --workspace --lib --examples
run_gate cargo-test-doc cargo test --workspace --doc
run_gate cargo-clippy cargo clippy --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --workspace --no-run
run_gate cargo-doc env "RUSTDOCFLAGS=-D warnings" cargo doc --workspace --no-deps

source_manifest >"$output/source-files.after.sha256"
cmp "$output/source-files.before.sha256" "$output/source-files.after.sha256"

{
    echo "status=PASS"
    echo "run_started_utc=$run_started_utc"
    echo "run_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
    echo "host_label=$host_label"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
} >"$output/run.status"
(
    cd "$output"
    rg --files -0 -g '!SHA256SUMS' \
        | sort -z \
        | xargs -0 sha256sum \
        >SHA256SUMS
    sha256sum --check --quiet SHA256SUMS
)

echo "host run: PASS"
