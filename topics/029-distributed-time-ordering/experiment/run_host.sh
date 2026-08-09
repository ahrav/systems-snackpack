#!/usr/bin/env bash
set -Eeuo pipefail

# The guards precede function definitions so compgen sees only inherited
# functions.
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source measurement refuses a BASH_ENV startup hook" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source measurement refuses inherited shell functions" >&2
    exit 2
fi
export GIT_NO_REPLACE_OBJECTS=1

if [[ $# -ne 4 ]]; then
    echo "usage: run_host.sh REPOSITORY OUTPUT HOST_LABEL SOURCE_COMMIT" >&2
    exit 2
fi

repository=$(realpath "$1")
output=$(realpath -m "$2")
host_label=$3
source_commit=$4
source_archive_sha256=not-recorded
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
cargo_home=
build_root=
run_completed=0

seal_evidence() {
    (
        cd "$output"
        manifest=.SHA256SUMS.tmp
        rm -f "$manifest"
        if ! find . -type f ! -name SHA256SUMS ! -name "$manifest" -print0 \
            | LC_ALL=C sort -z \
            | xargs -0 sha256sum >"$manifest"; then
            rm -f "$manifest"
            return 1
        fi
        mv "$manifest" SHA256SUMS || return 1
        sha256sum --check --quiet SHA256SUMS || return 1
    )
}

write_run_status() {
    local status=$1
    local exit_code=$2
    {
        echo "status=$status"
        echo "exit_code=$exit_code"
        echo "run_started_utc=$run_started_utc"
        echo "run_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
        printf 'host_label=%q\n' "$host_label"
        echo "source_commit=$source_commit"
        echo "source_archive_sha256=$source_archive_sha256"
    } >"$output/run.status"
}

finalize() {
    local exit_code=$?
    trap - EXIT
    set +e
    if [[ -d $output ]]; then
        if (( exit_code == 0 && run_completed == 1 )); then
            write_run_status success 0
        else
            if (( exit_code == 0 )); then
                exit_code=1
            fi
            write_run_status failed "$exit_code"
        fi
        if ! seal_evidence; then
            exit_code=1
            write_run_status failed 1
            printf 'failure_reason=evidence_seal_failed\n' >>"$output/run.status"
            seal_evidence || true
        fi
    fi
    if [[ -n $cargo_home && -f $cargo_home/.topic29-cargo-home ]]; then
        rm -rf "$cargo_home"
    fi
    if [[ -n $build_root && -f $build_root/.topic29-build-root ]]; then
        rm -rf "$build_root"
    fi
    exit "$exit_code"
}

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
if [[ -z $host_label || $host_label == *$'\n'* || $host_label == *$'\r'* ]]; then
    echo "host label must be non-empty and single-line" >&2
    exit 2
fi

mkdir -p "$output/gates"
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

repository_root=$(git -C "$repository" rev-parse --show-toplevel)
if [[ $(realpath "$repository_root") != "$repository" ]]; then
    echo "repository must be the root of its Git worktree" >&2
    exit 2
fi
current_head=$(git -C "$repository" rev-parse HEAD)
if [[ $current_head != "$source_commit" ]]; then
    echo "HEAD does not equal the requested source commit" >&2
    exit 2
fi
if [[ -n $(git -C "$repository" status --porcelain=v1 --untracked-files=all) ]]; then
    echo "exact-source measurement requires a clean worktree" >&2
    exit 2
fi
marked_files=$(git -C "$repository" ls-files -v)
if grep -Eq '^(S|[a-z]) ' <<<"$marked_files"; then
    echo "exact-source measurement refuses assume-unchanged or skip-worktree files" >&2
    exit 2
fi
if ! git -C "$repository" ls-files -z \
    | git -C "$repository" check-attr --stdin -z \
        filter ident export-ignore export-subst \
    | tr '\0' '\n' \
    | awk 'NR % 3 == 0 && $0 != "unspecified" && $0 != "unset" { bad = 1 } END { exit bad }'; then
    echo "exact-source measurement refuses content-transforming Git attributes" >&2
    exit 2
fi

git -C "$repository" archive --format=tar "$source_commit" \
    | gzip -n -9 >"$output/source.tar.gz"
source_archive_sha256=$(sha256sum "$output/source.tar.gz" | awk '{print $1}')

build_root=$(mktemp -d "${TMPDIR:-/tmp}/topic29-build-root.XXXXXXXX")
touch "$build_root/.topic29-build-root"
tar -xzf "$output/source.tar.gz" -C "$build_root"
topic="$build_root/topics/029-distributed-time-ordering"

{
    echo "swept_prefixes=CARGO_ RUST"
    while IFS= read -r variable; do
        case $variable in
            RUSTUP_HOME)
                printf 'kept %s=%q\n' "$variable" "${!variable}"
                ;;
            CARGO_* | RUST*)
                printf 'unset %s=%q\n' "$variable" "${!variable}"
                unset "$variable"
                ;;
        esac
    done < <(compgen -e | LC_ALL=C sort)
} >"$output/environment.before.txt"

pinned_toolchain=$(sed -n 's/^channel = "\(.*\)"$/\1/p' \
    "$build_root/rust-toolchain.toml")
resolved_rustc=$(cd "$build_root" && rustc --version | awk '{print $2}')
if [[ -z $pinned_toolchain || $resolved_rustc != "$pinned_toolchain" ]]; then
    printf 'resolved rustc %s does not match the pinned toolchain %s\n' \
        "$resolved_rustc" "${pinned_toolchain:-unparsed}" >&2
    exit 2
fi

cargo_home=$(mktemp -d "${TMPDIR:-/tmp}/topic29-cargo-home.XXXXXXXX")
touch "$cargo_home/.topic29-cargo-home"
export CARGO_HOME="$cargo_home"
printf 'CARGO_HOME=%q\n' "$CARGO_HOME" >"$output/environment.effective.txt"

config_scan_directory=$build_root
while :; do
    for cargo_config in \
        "$config_scan_directory/.cargo/config.toml" \
        "$config_scan_directory/.cargo/config"; do
        if [[ -e $cargo_config ]]; then
            echo "unrecorded Cargo config would alter builds: $cargo_config" >&2
            exit 2
        fi
    done
    if [[ $config_scan_directory == / ]]; then
        break
    fi
    config_scan_directory=$(dirname "$config_scan_directory")
done

{
    printf 'host_label=%q\n' "$host_label"
    echo "source_commit=$source_commit"
    echo "source_archive_sha256=$source_archive_sha256"
} >"$output/source_identity.txt"

(
    cd "$build_root"
    printf 'host_label=%q\n' "$host_label"
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
) >"$output/host.txt" 2>&1

{
    echo "generic: RUSTFLAGS unset"
    echo "native: RUSTFLAGS=-C target-cpu=native"
    echo "workspace gates: RUSTFLAGS unset"
} >"$output/build-flags.txt"

source_files() {
    (
        cd "$repository"
        rg --files -0 --hidden --no-ignore \
            -g '!.git/**' -g '!/target/**' \
            -g '!**/__pycache__/**' -g '!**/.ruff_cache/**' \
            | LC_ALL=C sort -z
    )
}

untracked_inputs=$(LC_ALL=C comm -13 \
    <(git -C "$repository" ls-files -z | tr '\0' '\n' | LC_ALL=C sort) \
    <(source_files | tr '\0' '\n'))
if [[ -n $untracked_inputs ]]; then
    printf 'untracked files would be measured as build inputs:\n%s\n' \
        "$untracked_inputs" >&2
    exit 2
fi

source_manifest() {
    (
        cd "$build_root"
        find . -type f \
            ! -path './target/*' \
            ! -path '*/__pycache__/*' \
            ! -name .topic29-build-root \
            -print0 \
            | LC_ALL=C sort -z \
            | xargs -0 sha256sum
    )
}

source_manifest >"$output/source-files.before.sha256"

run_gate() {
    local name=$1
    shift
    (
        cd "$build_root"
        "$@"
    ) >"$output/gates/$name.log" 2>&1
}

run_gate cargo-fmt cargo fmt --all -- --check

unset RUSTFLAGS || true
run_gate cargo-test-package-generic cargo test --locked \
    --package distributed-time-ordering
run_gate cargo-build-package-generic cargo build --locked --release \
    --package distributed-time-ordering --bin ordering-probe

generic_binary="$build_root/target/release/ordering-probe"
cp "$generic_binary" "$output/ordering-probe.generic"
sha256sum "$output/ordering-probe.generic" >"$output/binary.generic.sha256"
python3 "$topic/experiment/run_processes.py" \
    "$generic_binary" \
    "$output/experiment-generic" >"$output/process-runner.generic.log" 2>&1
python3 "$topic/experiment/validate_receipts.py" \
    "$output/experiment-generic" "$output/ordering-probe.generic" \
    >"$output/validation.generic.log" 2>&1
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

binary="$build_root/target/release/ordering-probe"
cp "$binary" "$output/ordering-probe.native"
sha256sum "$output/ordering-probe.native" >"$output/binary.native.sha256"
nm -n "$binary" >"$output/binary.symbols.txt"
symbols=(
    topic29_lww_choice
    topic29_lamport_receive
    topic29_vector_relation
    topic29_hlc_receive
)
for symbol in "${symbols[@]}"; do
    rg -q "[[:space:]][Tt][[:space:]]${symbol}$" \
        "$output/binary.symbols.txt"
    objdump -d --no-show-raw-insn --disassemble="$symbol" "$binary"
done >"$output/codegen.txt" 2>&1
for symbol in "${symbols[@]}"; do
    rg -q "<${symbol}>:" "$output/codegen.txt"
done

python3 "$topic/experiment/run_processes.py" "$binary" \
    "$output/experiment-native" >"$output/process-runner.native.log" 2>&1
python3 "$topic/experiment/validate_receipts.py" \
    "$output/experiment-native" "$output/ordering-probe.native" \
    >"$output/validation.native.log" 2>&1
native_recorded_sha256=$(awk 'NR == 1 { print $1 }' \
    "$output/experiment-native/binary.sha256")
native_actual_sha256=$(sha256sum "$output/ordering-probe.native" \
    | awk '{ print $1 }')
[[ $native_recorded_sha256 == "$native_actual_sha256" ]]

unset RUSTFLAGS
run_gate cargo-test-lib-examples cargo test --workspace --lib --bins --examples
run_gate cargo-test-doc cargo test --workspace --doc
run_gate cargo-clippy cargo clippy --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --workspace --no-run
run_gate cargo-doc env "RUSTDOCFLAGS=-D warnings" cargo doc --workspace --no-deps

source_manifest >"$output/source-files.after.sha256"
cmp "$output/source-files.before.sha256" "$output/source-files.after.sha256"

if [[ $(git -C "$repository" rev-parse HEAD) != "$source_commit" ]]; then
    echo "HEAD changed during the measurement run" >&2
    exit 1
fi
if [[ -n $(git -C "$repository" status --porcelain=v1 --untracked-files=all) ]]; then
    echo "worktree changed during the measurement run" >&2
    exit 1
fi

run_completed=1
echo "host run: PASS"
