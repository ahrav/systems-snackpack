#!/usr/bin/env bash
set -euo pipefail

# Run the committed Topic 39 correctness model from a digest-bound Git archive.
# Results and build products stay outside the extracted source tree.
if [[ -n ${BASH_ENV:-} ]]; then
    echo "exact-source experiment refuses BASH_ENV" >&2
    exit 2
fi
if [[ -n $(compgen -A function) ]]; then
    echo "exact-source experiment refuses inherited shell functions" >&2
    exit 2
fi
if [[ -s /etc/ld.so.preload ]]; then
    echo "exact-source experiment refuses system-wide dynamic-loader preloads" >&2
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
        PYTHONPATH | PYTHONHOME | RIPGREP_CONFIG_PATH | CDPATH)
        swept_environment_names+=("$variable")
        unset "$variable"
        ;;
    esac
done < <(compgen -e)
export GIT_NO_REPLACE_OBJECTS=1
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
source_archive=$(realpath -m -- "$4")
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
if [[ ! -f $source_archive ]]; then
    echo "source archive does not exist: $source_archive" >&2
    exit 2
fi

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

work_dir="${output_dir}.work"
extract_dir="$work_dir/archive"
mkdir -p "$output_dir" "$extract_dir"
tar -xzf "$source_archive" -C "$extract_dir"

runner_relative=topics/039-iommu-dma-device-memory/experiment/run_host.sh
mapfile -t runner_markers < <(rg --files --hidden --no-ignore "$extract_dir" | rg "/${runner_relative}$" | LC_ALL=C sort)
if [[ ${#runner_markers[@]} -ne 1 ]]; then
    echo "archive must contain exactly one Topic 39 host runner" >&2
    exit 2
fi
source_root=${runner_markers[0]%/"$runner_relative"}
source_root=$(realpath "$source_root")
experiment_dir="$source_root/topics/039-iommu-dma-device-memory/experiment"
if ! cmp -- "${BASH_SOURCE[0]}" "$experiment_dir/run_host.sh"; then
    echo "executed host runner differs from the archive's runner" >&2
    exit 2
fi

write_source_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z | xargs -0 sha256sum
    ) >"$destination"
}

run_gate() {
    local name=$1
    shift
    {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
    } >"$output_dir/$name" 2>&1
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
    printf 'source_archive=%s\n' "$source_archive"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'source_root=%s\n' "$source_root"
    printf 'runner_sha256='
    sha256sum "$experiment_dir/run_host.sh" | awk '{print $1}'
    printf 'swept_environment_names=%s\n' "${swept_environment_names[*]:-none}"
} >"$output_dir/source-identity.txt"

{
    printf 'date_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'hostname_short='; hostname
    printf 'hostname_fqdn=%s\n' "$resolved_hostname"
    printf 'uname_all='; uname -a
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel='; uname -r
    printf 'cpu_count_online='; getconf _NPROCESSORS_ONLN
    printf 'cpu_count_available='; nproc
    printf 'page_size='; getconf PAGESIZE
    printf 'build_generic=release default target features\n'
    printf 'build_native=release RUSTFLAGS=-C target-cpu=native\n'
    printf 'measurement_kind=deterministic correctness only\n'
    printf 'fresh_process_runs=8 generic + 8 native\n'
    printf 'timing_reported=no\n'
    printf 'real_dma_exercised=no\n'
    lscpu
} >"$output_dir/host.txt" 2>&1

record_optional proc-cpuinfo.txt sed -n '1,260p' /proc/cpuinfo
record_optional rustc-version.txt rustc -vV
record_optional cargo-version.txt cargo -Vv
record_optional python-version.txt python3 -VV
record_optional cc-version.txt cc -v
record_optional objdump-version.txt objdump --version
record_optional rust-target-cfg.txt rustc --print cfg
record_optional rust-target-features.txt rustc --print target-features
record_optional cc-native-target.txt cc -march=native -Q --help=target
record_optional limits.txt bash -c 'ulimit -a'

shopt -s nullglob
iommu_class_entries=(/sys/class/iommu/*)
iommu_group_entries=(/sys/kernel/iommu_groups/*)
pci_devices=(/sys/bus/pci/devices/*)
pci_iommu_links=0
for device in "${pci_devices[@]}"; do
    if [[ -L $device/iommu_group ]]; then
        ((pci_iommu_links += 1))
    fi
done
{
    printf 'sys_class_iommu_entries=%d\n' "${#iommu_class_entries[@]}"
    printf 'sys_kernel_iommu_groups=%d\n' "${#iommu_group_entries[@]}"
    printf 'sys_bus_pci_devices=%d\n' "${#pci_devices[@]}"
    printf 'pci_devices_with_iommu_group_link=%d\n' "$pci_iommu_links"
    printf 'sys_class_iommu_listing_begin\n'
    for entry in "${iommu_class_entries[@]}"; do
        printf '%s -> %s\n' "$entry" "$(realpath "$entry")"
    done
    printf 'sys_class_iommu_listing_end\n'
    printf 'iommu_group_listing_begin\n'
    for entry in "${iommu_group_entries[@]}"; do
        printf '%s\n' "$entry"
    done
    printf 'iommu_group_listing_end\n'
} >"$output_dir/iommu-sysfs.txt"

kernel_pattern='^(CONFIG_(IOMMU|IOMMUFD|IOMMU_SVA|SWIOTLB|ARM_SMMU|ARM_SMMU_V3|INTEL_IOMMU|AMD_IOMMU|VFIO|VFIO_IOMMU_TYPE1|PCI_PASID|PCI_ATS|PCI_PRI))='
{
    if [[ -r /proc/config.gz ]]; then
        printf 'kernel_config_source=/proc/config.gz\n'
        gzip -dc /proc/config.gz | rg "$kernel_pattern" || true
    elif [[ -r /boot/config-$(uname -r) ]]; then
        printf 'kernel_config_source=/boot/config-%s\n' "$(uname -r)"
        rg "$kernel_pattern" "/boot/config-$(uname -r)" || true
    else
        printf 'kernel_config_source=unavailable\n'
    fi
} >"$output_dir/iommu-kernel-config.txt" 2>&1

cargo_target="$work_dir/cargo-target-generic"
native_cargo_target="$work_dir/cargo-target-native"
manifest="$source_root/Cargo.toml"
package=iommu-dma-device-memory
run_gate gate-cargo-fmt.txt cargo fmt --manifest-path "$manifest" --all -- --check
run_gate gate-cargo-test.txt env CARGO_TARGET_DIR="$cargo_target" cargo test --manifest-path "$manifest" --locked --offline --package "$package" --all-targets
run_gate gate-cargo-clippy.txt env CARGO_TARGET_DIR="$cargo_target" cargo clippy --manifest-path "$manifest" --locked --offline --package "$package" --all-targets -- -D warnings
run_gate gate-cargo-doc.txt env CARGO_TARGET_DIR="$cargo_target" RUSTDOCFLAGS=-Dwarnings cargo doc --manifest-path "$manifest" --locked --offline --package "$package" --no-deps
run_gate build-generic.txt env CARGO_TARGET_DIR="$cargo_target" RUSTFLAGS= cargo build --manifest-path "$manifest" --locked --offline --release --package "$package" --bin dma-contract-probe
run_gate build-native.txt env CARGO_TARGET_DIR="$native_cargo_target" RUSTFLAGS='-C target-cpu=native' cargo build --manifest-path "$manifest" --locked --offline --release --package "$package" --bin dma-contract-probe

generic_binary="$cargo_target/release/dma-contract-probe"
native_binary="$native_cargo_target/release/dma-contract-probe"
expected="$experiment_dir/expected.txt"
process_root="$output_dir/processes"
mkdir "$process_root"
run_gate run-generic-processes.txt python3 -I -B "$experiment_dir/run_processes.py" \
    --binary "$generic_binary" --expected "$expected" \
    --output "$process_root/generic" --flavor generic --runs 8
run_gate run-native-processes.txt python3 -I -B "$experiment_dir/run_processes.py" \
    --binary "$native_binary" --expected "$expected" \
    --output "$process_root/native" --flavor native --runs 8
run_gate validate-process-receipts.txt python3 -I -B "$experiment_dir/validate_receipts.py" \
    --root "$process_root" --expected "$expected"

codegen="$output_dir/codegen"
mkdir "$codegen"
for flavor in generic native; do
    binary="$generic_binary"
    if [[ $flavor == native ]]; then
        binary="$native_binary"
    fi
    objdump -drwC "$binary" >"$codegen/${flavor}.objdump.txt"
    nm -n "$binary" >"$codegen/${flavor}.symbols.txt"
    readelf -h -n -A "$binary" >"$codegen/${flavor}.elf.txt"
    readelf -rW "$binary" >"$codegen/${flavor}.relocations.txt"
    # `|| true`: a missing symbol must reach the named error below, not die
    # silently on rg's non-match exit status under `set -e`.
    rg -n '<topic39_(checked_translate|mask_allows)>:' \
        "$codegen/${flavor}.objdump.txt" >"$codegen/${flavor}.required-symbols.txt" \
        || true
    for symbol in topic39_checked_translate topic39_mask_allows; do
        if ! rg -q "<${symbol}>:" "$codegen/${flavor}.objdump.txt"; then
            echo "$flavor codegen lacks required definition $symbol" >&2
            exit 1
        fi
        if rg -q "[[:space:]](callq?|bl)[[:space:]]+[^<]*<${symbol}>" \
            "$codegen/${flavor}.objdump.txt"; then
            printf '%s\t%s\tdirect-symbol-call\n' "$flavor" "$symbol" \
                >>"$codegen/linked-hook-modes.tsv"
        elif [[ $architecture == x86_64 ]]; then
            # Position-independent x86-64 executables can load this locally
            # defined function through a relative relocation and then use an
            # indirect register call. Bind the whole chain: the relocation
            # names a slot holding the symbol's linked address, an
            # instruction loads that exact slot (objdump resolves the
            # rip-relative target in its comment), and a later call goes
            # through the loaded register before anything clobbers it, or
            # calls through the slot memory-indirectly. An unrelated indirect
            # call elsewhere in the binary cannot satisfy this. The
            # deterministic probe output separately proves that both hook
            # results passed their assertions.
            symbol_address=$(
                awk -v symbol="$symbol" '$3 == symbol { print $1; exit }' \
                    "$codegen/${flavor}.symbols.txt" | sed 's/^0*//'
            )
            slot_addresses=$(
                awk -v target="$symbol_address" \
                    '$3 == "R_X86_64_RELATIVE" && $4 == target {
                        slot = $1; sub(/^0+/, "", slot); print slot
                    }' "$codegen/${flavor}.relocations.txt" | paste -sd,
            )
            if [[ -z $symbol_address || -z $slot_addresses ]] || \
                ! awk -v slots_str="$slot_addresses" '
                    BEGIN {
                        n = split(slots_str, parts, ",")
                        for (i = 1; i <= n; i++) if (parts[i] != "") slot[parts[i]] = 1
                    }
                    # A new function body invalidates every tracked register.
                    /^[0-9a-f]+ </ { for (r in pending) delete pending[r]; next }
                    {
                        line = $0
                        # Memory-indirect call straight through a hook slot.
                        if (line ~ /callq?[[:space:]]+\*0x[0-9a-f]+\(%rip\)[[:space:]]+#/) {
                            cmt = line
                            sub(/.*#[[:space:]]*/, "", cmt); sub(/[[:space:]<].*/, "", cmt)
                            if (cmt in slot) { found = 1; exit }
                            next
                        }
                        # Load of a hook slot into a register.
                        if (line ~ /mov[[:space:]]+0x[0-9a-f]+\(%rip\),%r[0-9a-z]+[[:space:]]+#/) {
                            reg = line
                            sub(/.*\(%rip\),/, "", reg); sub(/[[:space:]].*/, "", reg)
                            cmt = line
                            sub(/.*#[[:space:]]*/, "", cmt); sub(/[[:space:]<].*/, "", cmt)
                            if (cmt in slot) { pending[reg] = 1 } else { delete pending[reg] }
                            next
                        }
                        # Register-indirect call through a still-live hook register.
                        if (line ~ /callq?[[:space:]]+\*%r[0-9a-z]+/) {
                            reg = line
                            sub(/.*\*/, "", reg); sub(/[[:space:]].*/, "", reg)
                            if (reg in pending) { found = 1; exit }
                            next
                        }
                        # Any other write to a tracked register invalidates it.
                        op = line
                        sub(/[[:space:]]*#.*$/, "", op)
                        if (match(op, /,%r[0-9a-z]+$/)) {
                            reg = substr(op, RSTART + 1, RLENGTH - 1)
                            delete pending[reg]
                        }
                    }
                    END { exit found ? 0 : 1 }
                ' "$codegen/${flavor}.objdump.txt"; then
                echo "$flavor codegen lacks a linked direct or slot-bound indirect call to $symbol" >&2
                exit 1
            fi
            printf '%s\t%s\tx86-slot-bound-indirect-call\n' \
                "$flavor" "$symbol" >>"$codegen/linked-hook-modes.tsv"
        else
            echo "$flavor codegen lacks a linked call to $symbol" >&2
            exit 1
        fi
    done
done

{
    printf 'generic_binary_sha256='; sha256sum "$generic_binary" | awk '{print $1}'
    printf 'native_binary_sha256='; sha256sum "$native_binary" | awk '{print $1}'
    printf 'expected_output_sha256='; sha256sum "$expected" | awk '{print $1}'
} >"$output_dir/artifact-identity.txt"

write_source_manifest "$output_dir/source-manifest-after.sha256"
if ! cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"; then
    echo "source tree changed during the exact-source experiment" >&2
    exit 1
fi
{
    printf 'source_identity=verified_archive_commit_and_sha256\n'
    printf 'source_manifest_unchanged=yes\n'
    printf 'host_identity=verified_label_resolved_hostname_and_architecture\n'
    printf 'correctness_processes=16\n'
    printf 'generic_processes=8\n'
    printf 'native_processes=8\n'
    printf 'generated_code=hook_definitions_and_direct_or_relocated_indirect_calls_verified\n'
    printf 'measurement_boundary=CPU_only_contract_model_no_real_DMA_or_IOMMU_activity\n'
    printf 'timing_reported=no\n'
    printf 'result=PASS\n'
} >"$output_dir/completion.txt"

if [[ $work_dir != "${output_dir}.work" || ! -d $work_dir ]]; then
    echo "refusing cleanup outside the newly created work directory" >&2
    exit 2
fi
rm -rf -- "$work_dir"

manifest_tmp="${output_dir}.manifest.$$.tmp"
if [[ -e $manifest_tmp ]]; then
    echo "temporary manifest path already exists: $manifest_tmp" >&2
    exit 2
fi
(
    cd "$output_dir"
    rg --files --hidden --no-ignore -0 | LC_ALL=C sort -z | xargs -0 sha256sum
) >"$manifest_tmp"
mv -- "$manifest_tmp" "$output_dir/MANIFEST.sha256"
printf 'HOST_RUN=PASS output=%s\n' "$output_dir"
