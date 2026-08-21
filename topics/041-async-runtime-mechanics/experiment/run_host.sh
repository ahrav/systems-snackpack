#!/usr/bin/env bash
set -euo pipefail

# Replay the committed Topic 41 probe from a digest-bound Git archive. Build
# products and receipts stay outside the extracted source tree.
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source experiment refuses BASH_ENV" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source experiment refuses inherited shell functions" >&2
    exit 2
fi
if [[ -s /etc/ld.so.preload ]]; then
    echo "exact-source experiment refuses /etc/ld.so.preload" >&2
    exit 2
fi

swept_environment_names=()
while IFS= read -r variable; do
    case $variable in
    RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTDOC | RUSTFMT | \
        RUSTFLAGS | RUSTDOCFLAGS | CARGO_ENCODED_RUSTFLAGS | CARGO_INCREMENTAL | \
        CARGO_BUILD_* | CARGO_TARGET_* | CARGO_PROFILE_* | CARGO_UNSTABLE_* | \
        CC | CFLAGS | CPPFLAGS | LDFLAGS | COMPILER_PATH | GCC_EXEC_PREFIX | \
        LIBRARY_PATH | CPATH | C_INCLUDE_PATH | CPLUS_INCLUDE_PATH | \
        LD_* | DYLD_* | GLIBC_TUNABLES | MALLOC_* | GIT_* | \
        TAR_OPTIONS | TAPE | GZIP | PYTHONPATH | PYTHONHOME | \
        RIPGREP_CONFIG_PATH | CDPATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
export GIT_NO_REPLACE_OBJECTS=1
export LC_ALL=C
export LANG=C
export PATH="$HOME/.cargo/bin:/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
hash -r

if [[ $# -ne 4 ]]; then
    echo "usage: $0 OUTPUT_DIR SOURCE_COMMIT SOURCE_ARCHIVE_SHA256 SOURCE_ARCHIVE" >&2
    exit 2
fi
: "${SSH_TARGET_LABEL:?set SSH_TARGET_LABEL to xxl or the authorized Arm hostname}"
: "${SSH_RESOLVED_HOSTNAME:?set SSH_RESOLVED_HOSTNAME to the runtime-resolved hostname}"

output_dir=$(realpath -m -- "$1")
source_commit=${2,,}
archive_digest_expected=${3,,}
caller_archive=$(realpath -m -- "$4")
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "SOURCE_COMMIT must be a full 40-hex Git object ID" >&2
    exit 2
fi
if [[ ! $archive_digest_expected =~ ^[0-9a-f]{64}$ ]]; then
    echo "SOURCE_ARCHIVE_SHA256 must be 64 hexadecimal digits" >&2
    exit 2
fi
if [[ -e $output_dir || -e ${output_dir}.work ]]; then
    echo "output or work path already exists: $output_dir" >&2
    exit 2
fi
if [[ ! -f $caller_archive ]]; then
    echo "source archive does not exist: $caller_archive" >&2
    exit 2
fi

output_parent=$(dirname -- "$output_dir")
if [[ -L $output_parent || ! -d $output_parent ]]; then
    echo "output parent must exist as a real directory: $output_parent" >&2
    exit 2
fi
mkdir -m 0700 -- "$output_dir" "${output_dir}.work"
work_dir="${output_dir}.work"
extract_dir="$work_dir/archive"
mkdir -m 0700 -- "$extract_dir"

# Work from one private archive snapshot so a caller cannot replace the input
# between digest verification and extraction. Retain the snapshot with the
# receipts so the exact candidate can be audited later.
source_archive="$output_dir/source-archive.tar.gz"
cp -- "$caller_archive" "$source_archive"
chmod 0400 "$source_archive"
archive_digest=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $archive_digest != "$archive_digest_expected" ]]; then
    echo "source archive digest mismatch" >&2
    exit 2
fi
pax_global_header=$(gzip -dc -- "$source_archive" 2>/dev/null | dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_global_header =~ comment=([0-9a-f]{40}) ]]; then
    echo "archive lacks the commit identity written by git archive" >&2
    exit 2
fi
if [[ ${BASH_REMATCH[1]} != "$source_commit" ]]; then
    echo "archive embeds ${BASH_REMATCH[1]}, not $source_commit" >&2
    exit 2
fi
if tar -tzf "$source_archive" | rg '(^/|(^|/)\.\.(/|$))'; then
    echo "source archive contains an unsafe path" >&2
    exit 2
fi
if tar -tvzf "$source_archive" | awk 'substr($1, 1, 1) == "l" { found=1 } END { exit !found }'; then
    echo "source archive contains a symbolic link" >&2
    exit 2
fi

resolved_hostname=$(hostname -f)
architecture=$(uname -m)
if [[ $resolved_hostname != "$SSH_RESOLVED_HOSTNAME" ]]; then
    echo "resolved host mismatch: expected $SSH_RESOLVED_HOSTNAME, got $resolved_hostname" >&2
    exit 1
fi
case $SSH_TARGET_LABEL in
xxl)
    [[ $architecture == x86_64 ]] || {
        echo "xxl must resolve to x86_64; got $architecture" >&2
        exit 1
    }
    ;;
dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com)
    [[ $architecture == aarch64 || $architecture == arm64 ]] || {
        echo "authorized Arm host must be aarch64/arm64; got $architecture" >&2
        exit 1
    }
    ;;
*)
    echo "unexpected SSH target label: $SSH_TARGET_LABEL" >&2
    exit 2
    ;;
esac

tar -xzf "$source_archive" -C "$extract_dir"
runner_relative=topics/041-async-runtime-mechanics/experiment/run_host.sh
mapfile -t runner_markers < <(rg --files --hidden --no-ignore "$extract_dir" | rg "/${runner_relative}$" | LC_ALL=C sort)
if [[ ${#runner_markers[@]} -ne 1 ]]; then
    echo "archive must contain exactly one Topic 41 host runner" >&2
    exit 2
fi
source_root=${runner_markers[0]%/"$runner_relative"}
source_root=$(realpath "$source_root")
topic_dir="$source_root/topics/041-async-runtime-mechanics"
experiment_dir="$topic_dir/experiment"
example="$topic_dir/examples/state_and_cancellation.rs"
if ! cmp -- "${BASH_SOURCE[0]}" "$experiment_dir/run_host.sh"; then
    echo "executed host runner differs from the archive's runner" >&2
    exit 2
fi
example_digest=$(sha256sum "$example" | awk '{print $1}')
expected_example_digest=c25a1520bbedbd412360271f004976a3aaa777051bccce5e31302cf7ba79afe6
if [[ $example_digest != "$expected_example_digest" ]]; then
    echo "example bytes differ from the researched source: $example_digest" >&2
    exit 2
fi

write_source_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum --
    ) >"$destination"
}

record_required() {
    local name=$1
    shift
    if ! {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1; then
        echo "required evidence command failed: $name" >&2
        exit 1
    fi
}

record_optional() {
    local name=$1
    shift
    {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1 || true
}

write_source_manifest "$output_dir/source-manifest-before.sha256"
{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'source_archive_retained=source-archive.tar.gz\n'
    printf 'example_relative_path=topics/041-async-runtime-mechanics/examples/state_and_cancellation.rs\n'
    printf 'example_sha256=%s\n' "$example_digest"
    printf 'runner_sha256='; sha256sum "$experiment_dir/run_host.sh" | awk '{print $1}'
    printf 'process_runner_sha256='; sha256sum "$experiment_dir/run_processes.py" | awk '{print $1}'
    printf 'receipt_validator_sha256='; sha256sum "$experiment_dir/validate_receipts.py" | awk '{print $1}'
    printf 'swept_environment_names=%s\n' "${swept_environment_names[*]:-none}"
} >"$output_dir/source-identity.txt"

build_flags=(
    --edition=2024
    -C opt-level=3
    -C debuginfo=1
    -C codegen-units=1
    -C lto=no
    -C panic=abort
    -C target-cpu=native
)
{
    printf 'captured_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_target_label_trust=caller_supplied_not_verifiable_on_host\n'
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'hostname_fqdn=%s\n' "$resolved_hostname"
    printf 'uname_all='; uname -a
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel='; uname -r
    printf 'cpu_count_online='; getconf _NPROCESSORS_ONLN
    printf 'cpu_count_available='; nproc
    printf 'page_size='; getconf PAGESIZE
    printf 'build_flags=%s\n' "${build_flags[*]}"
    printf 'fresh_process_runs=8\n'
    printf 'measurement_kind=deterministic correctness and generated code\n'
    printf 'timing_reported=no\n'
    lscpu
} >"$output_dir/host.txt" 2>&1

record_required proc-cpuinfo.txt rg -n -m 320 \
    '^(processor|vendor_id|model name|CPU implementer|CPU architecture|CPU variant|CPU part|CPU revision|Features)[[:space:]]*:' \
    /proc/cpuinfo
record_required rustc-version.txt rustc -vV
record_required cargo-version.txt cargo -Vv
record_required rustfmt-version.txt rustfmt -V
record_required clippy-version.txt cargo clippy -V
record_required python-version.txt python3 -VV
record_required objdump-version.txt objdump --version
record_required readelf-version.txt readelf --version
record_required nm-version.txt nm --version
record_required linker-version.txt ld --version
record_required rust-target-cfg.txt rustc --print cfg
record_required rust-native-target-cfg.txt rustc -C target-cpu=native --print cfg
record_required rust-target-features.txt rustc --print target-features
record_optional rust-native-target-features.txt rustc -C target-cpu=native --print target-features
record_optional limits.txt bash -c 'ulimit -a'

cargo_target="$work_dir/cargo-target"
record_required gate-cargo-fmt.txt env CARGO_TARGET_DIR="$cargo_target" cargo fmt --manifest-path "$source_root/Cargo.toml" --all -- --check
record_required gate-cargo-test.txt env CARGO_TARGET_DIR="$cargo_target" cargo test --manifest-path "$source_root/Cargo.toml" --locked --package async-runtime-mechanics --lib --examples
record_required gate-cargo-test-doc.txt env CARGO_TARGET_DIR="$cargo_target" cargo test --manifest-path "$source_root/Cargo.toml" --locked --package async-runtime-mechanics --doc
record_required gate-cargo-clippy.txt env CARGO_TARGET_DIR="$cargo_target" cargo clippy --manifest-path "$source_root/Cargo.toml" --locked --package async-runtime-mechanics --all-targets -- -D warnings
record_required gate-cargo-bench-build.txt env CARGO_TARGET_DIR="$cargo_target" cargo bench --manifest-path "$source_root/Cargo.toml" --locked --package async-runtime-mechanics --no-run
record_required gate-cargo-doc.txt env CARGO_TARGET_DIR="$cargo_target" RUSTDOCFLAGS=-Dwarnings cargo doc --manifest-path "$source_root/Cargo.toml" --locked --package async-runtime-mechanics --no-deps

codegen_dir="$output_dir/codegen"
mkdir -m 0700 -- "$codegen_dir"
rustc "${build_flags[@]}" "$example" -o "$codegen_dir/probe"
rustc "${build_flags[@]}" --emit=asm "$example" -o "$codegen_dir/probe.s"
rustc "${build_flags[@]}" --emit=obj "$example" -o "$codegen_dir/probe.o"
rustc "${build_flags[@]}" --emit=mir "$example" -o "$codegen_dir/probe.mir"
sha256sum "$codegen_dir"/probe "$codegen_dir"/probe.s "$codegen_dir"/probe.o "$codegen_dir"/probe.mir >"$output_dir/generated.sha256"
readelf -h "$codegen_dir/probe" >"$output_dir/elf-header.txt"
readelf -n "$codegen_dir/probe" >"$output_dir/elf-notes.txt"
size "$codegen_dir/probe" "$codegen_dir/probe.o" >"$output_dir/code-size.txt"
nm -S --size-sort -C "$codegen_dir/probe" >"$output_dir/symbols.txt"
objdump -d -C --no-show-raw-insn "$codegen_dir/probe" >"$output_dir/disassembly.txt"
rg 'YieldOnce|UnsafeTake|SafeTake|run_(un)?safe_race|poll_once' "$output_dir/symbols.txt" >"$output_dir/focused-symbols.txt"
rg -n -A 28 'fn holds_large_value_across_yield::\{closure#0\}|fn finishes_large_value_before_yield::\{closure#0\}' "$codegen_dir/probe.mir" >"$output_dir/focused-mir.txt"
awk '
    /<.*YieldOnce.*Future.*poll.*>:/ ||
    /<.*UnsafeTake.*Future.*poll.*>:/ ||
    /<.*SafeTake.*Future.*poll.*>:/ {
        showing = 1
    }
    showing { print }
    showing && /^$/ { showing = 0 }
' "$output_dir/disassembly.txt" >"$output_dir/focused-disassembly.txt"

python3 "$experiment_dir/run_processes.py" \
    --binary "$codegen_dir/probe" \
    --output "$output_dir/processes" \
    --runs 8
python3 "$experiment_dir/validate_receipts.py" \
    --root "$output_dir/processes" >"$output_dir/receipt-validation.txt"

write_source_manifest "$output_dir/source-manifest-after.sha256"
cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"
(
    cd "$output_dir"
    rg --files -0 | LC_ALL=C sort -z | xargs -0 sha256sum --
) >"$work_dir/evidence.sha256"
mv "$work_dir/evidence.sha256" "$output_dir/evidence.sha256"

printf 'source_commit=%s\n' "$source_commit"
printf 'source_archive_sha256=%s\n' "$archive_digest"
printf 'example_sha256=%s\n' "$example_digest"
cat "$output_dir/processes/canonical.stdout"
cat "$output_dir/receipt-validation.txt"
printf 'outcome=PASS\n'
