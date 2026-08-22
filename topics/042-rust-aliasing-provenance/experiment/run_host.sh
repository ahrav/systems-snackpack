#!/bin/bash -p
set -euo pipefail

# Run the exact archived Topic 42 source. All build products and receipts stay
# below the caller-supplied /tmp result directory. The experiment reports no
# timing because its claim concerns language and compiler contracts, not speed.
#
# The fixed interpreter path and -p above are load-bearing. Bash sources
# $BASH_ENV before the first line of this file, so an in-script check cannot
# see a startup file that ran commands and then unset the variable; privileged
# mode suppresses that sourcing, and also discards environment-supplied shell
# functions and ignores SHELLOPTS, BASHOPTS, CDPATH, and GLOBIGNORE. Because
# an explicit `bash script` invocation bypasses this shebang, refuse to run
# when privileged mode is not already active rather than emitting receipts a
# startup hook could have influenced.
if [[ $- != *p* ]]; then
    echo "exact-source experiment requires privileged bash: run $0 directly" >&2
    exit 2
fi
# Privileged mode is not the dynamic loader's secure-execution mode: for an
# ordinary same-UID invocation the loader still honours the LD_* family for this
# interpreter. LD_PRELOAD and LD_AUDIT load a library directly, and
# LD_LIBRARY_PATH can satisfy one of Bash's own dependencies from an
# attacker-chosen directory; in every case the library's initialisation code has
# already run before this line and unsetting the variable afterwards cannot
# unload it. A compromised interpreter cannot sanitise itself, so refuse to
# certify the run instead of continuing. Removing these variables before the
# interpreter starts belongs to the launcher; see the trusted-launcher boundary
# below.
while IFS= read -r variable; do
    case $variable in
    LD_* | DYLD_*)
        echo "exact-source experiment refuses $variable" >&2
        exit 2
        ;;
    esac
done < <(compgen -e)
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

# Trusted-launcher boundary. The checks above refuse a run whose interpreter may
# already be instrumented, but they cannot prove it is clean: LD_PRELOAD,
# LD_AUDIT, and $BASH_ENV all act before the first line of this file, and a
# library already mapped into this process could equally suppress the refusals.
# What the caller supplies is therefore part of the evidence boundary. The
# launcher must start this script from a clean environment on a host whose
# /bin/bash, coreutils, binutils, git, python3, and rustup toolchain the reader
# already trusts. The receipts record the resolved command path, tool paths, and
# tool versions so that boundary is auditable; they do not extend it.

swept_environment_names=()
while IFS= read -r variable; do
    case $variable in
    RUSTC | RUSTC_WRAPPER | RUSTC_WORKSPACE_WRAPPER | RUSTDOC | RUSTFMT | \
        RUSTFLAGS | RUSTDOCFLAGS | RUSTUP_HOME | RUSTUP_TOOLCHAIN | CARGO_* | \
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
# Git reads system and global configuration even with HOME bound to the invoking
# account, and settings there change what the gates measure: core.whitespace can
# make `git diff --check` exit zero on trailing whitespace, and core.fsmonitor
# names a command Git runs while inspecting the work tree. Point both scopes at
# /dev/null so only the explicit -c settings below apply.
export GIT_CONFIG_GLOBAL=/dev/null
export GIT_CONFIG_SYSTEM=/dev/null

# Establish a trusted system-only search path before running any external
# command. Every check above uses shell builtins, so this is the first point at
# which an inherited PATH could matter, and the account resolution below must not
# depend on one: a substituted id, getent, or awk could otherwise name an
# attacker-controlled home whose .cargo/bin holds proxies that report the pinned
# version while producing different artifacts.
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin
hash -r

# The command path and the toolchain stores must not depend on an inherited HOME
# or RUSTUP_HOME. Privileged mode preserves both, and the rustup proxies compute
# their settings and toolchain directories from RUSTUP_HOME even when
# RUSTUP_TOOLCHAIN is cleared, so a linked or custom toolchain in a supplied home
# could report the pinned version from a different compiler. Resolve the invoking
# account from the password database using the kernel-reported real user, then
# bind HOME and RUSTUP_HOME to that account. The proxy directory is deliberately
# kept off PATH: the Rust tools are invoked by the absolute paths verified below,
# so neither a system rustc or cargo earlier in the path nor a poisoned
# .cargo/bin entry can be selected.
real_user=$(id -un)
account_home=$(getent passwd "$real_user" | awk -F: '{print $6}')
if [[ -z $account_home || ! -d $account_home ]]; then
    echo "cannot resolve a home directory for $real_user from the password database" >&2
    exit 2
fi
rustup_home="$account_home/.rustup"
rustup_bin="$account_home/.cargo/bin"
rustup_exe="$rustup_bin/rustup"
if [[ ! -d $rustup_home ]]; then
    echo "no rustup home for $real_user at $rustup_home" >&2
    exit 2
fi
if [[ ! -x $rustup_exe ]]; then
    echo "no rustup executable for $real_user at $rustup_exe" >&2
    exit 2
fi
export HOME="$account_home"
export RUSTUP_HOME="$rustup_home"
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
if [[ $(dirname -- "$output_dir") != /tmp ]]; then
    echo "OUTPUT_DIR must be a direct child of /tmp" >&2
    exit 2
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
    echo "SOURCE_COMMIT must be a full 40-hex Git object ID" >&2
    exit 2
fi
if [[ ! $archive_digest_expected =~ ^[0-9a-f]{64}$ ]]; then
    echo "SOURCE_ARCHIVE_SHA256 must be 64 hexadecimal digits" >&2
    exit 2
fi
if [[ -e $output_dir ]]; then
    echo "output already exists: $output_dir" >&2
    exit 2
fi
if [[ ! -f $source_archive ]]; then
    echo "source archive does not exist: $source_archive" >&2
    exit 2
fi

mkdir -m 0700 -- "$output_dir"
work_dir="$output_dir/.work"
extract_dir="$work_dir/archive"
mkdir -m 0700 -- "$work_dir" "$extract_dir"

# Cargo reads $CARGO_HOME/config.toml regardless of --locked and --offline, so
# an ambient home could add build.rustflags or select a wrapper or linker that
# host.txt never records. Redirect Cargo at an empty private home for the whole
# run. Every workspace dependency is another workspace member, so an empty
# registry cache still satisfies the offline gates.
cargo_home="$work_dir/cargo-home"
mkdir -m 0700 -- "$cargo_home"
export CARGO_HOME="$cargo_home"

private_archive="$work_dir/source-archive.tar.gz"
cp -- "$source_archive" "$private_archive"
chmod 0400 "$private_archive"

archive_digest=$(sha256sum "$private_archive" | awk '{print $1}')
if [[ $archive_digest != "$archive_digest_expected" ]]; then
    echo "source archive digest mismatch" >&2
    exit 2
fi
pax_global_header=$(gzip -dc -- "$private_archive" 2>/dev/null | dd bs=512 skip=1 count=1 status=none | tr -d '\0' || true)
if [[ ! $pax_global_header =~ comment=([0-9a-f]{40}) ]]; then
    echo "archive lacks the commit identity written by git archive" >&2
    exit 2
fi
archive_embedded_commit=${BASH_REMATCH[1]}
if [[ $archive_embedded_commit != "$source_commit" ]]; then
    echo "archive embeds $archive_embedded_commit, not $source_commit" >&2
    exit 2
fi
if tar -tzf "$private_archive" | rg '(^/|(^|/)\.\.(/|$))'; then
    echo "source archive contains an unsafe path" >&2
    exit 2
fi
if tar -tvzf "$private_archive" | awk 'substr($1, 1, 1) == "l" { found=1 } END { exit !found }'; then
    echo "source archive contains a symbolic link" >&2
    exit 2
fi
tar -xzf "$private_archive" -C "$extract_dir"

runner_relative=topics/042-rust-aliasing-provenance/experiment/run_host.sh
mapfile -t runner_markers < <(
    rg --files --hidden --no-ignore "$extract_dir" |
        rg "/${runner_relative}$" |
        LC_ALL=C sort
)
if [[ ${#runner_markers[@]} -ne 1 ]]; then
    echo "archive must contain exactly one Topic 42 host runner" >&2
    exit 2
fi
source_root=${runner_markers[0]%/"$runner_relative"}
source_root=$(realpath -- "$source_root")
topic_dir="$source_root/topics/042-rust-aliasing-provenance"
experiment_dir="$topic_dir/experiment"
if ! cmp -- "${BASH_SOURCE[0]}" "$experiment_dir/run_host.sh"; then
    echo "executed host runner differs from the archive's runner" >&2
    exit 2
fi

# Cargo, rustfmt, and Clippy each search the working directory and every ancestor
# for configuration, and CARGO_HOME isolation does not affect that search. The
# extracted tree sits below /tmp, so a file above it still reaches these builds:
# a /tmp/.cargo/config.toml can add build.rustflags or select a wrapper or linker,
# and a /tmp/rustfmt.toml setting disable_all_formatting turns the formatting gate
# into a pass. Every directory below OUTPUT_DIR is created by this run, so refuse
# any such configuration outside the digest-bound source tree.
ancestor=$(dirname -- "$source_root")
while :; do
    for ambient_config in .cargo/config.toml .cargo/config rustfmt.toml .rustfmt.toml \
        clippy.toml .clippy.toml; do
        if [[ -e $ancestor/$ambient_config ]]; then
            echo "refusing build configuration outside the source tree: $ancestor/$ambient_config" >&2
            exit 2
        fi
    done
    [[ $ancestor == / ]] && break
    ancestor=$(dirname -- "$ancestor")
done

write_source_manifest() {
    local destination=$1
    (
        cd "$source_root"
        rg --files --hidden --no-ignore -g '!target/**' -g '!.git/**' -g '!.git' -0 |
            LC_ALL=C sort -z |
            xargs -0 sha256sum --
    ) >"$destination"
}

run_record() {
    local destination=$1
    local command_status
    shift
    if {
        printf 'COMMAND='
        printf '%q ' "$@"
        printf '\n'
        "$@"
        command_status=$?
        printf 'EXIT_STATUS=%d\n' "$command_status"
        ((command_status == 0))
    } >"$output_dir/$destination" 2>&1; then
        return 0
    else
        echo "required command failed; see $output_dir/$destination" >&2
        exit 1
    fi
}

write_source_manifest "$output_dir/source-manifest-before.sha256"

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
    [[ $resolved_hostname == "$SSH_TARGET_LABEL" ]] || {
        echo "fixed Arm label must equal the executing hostname" >&2
        exit 1
    }
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

# Resolve rustup's pinned toolchain and all Cargo metadata from the archived
# workspace itself. The records below therefore describe the tools used by the
# gates and native build.
cd "$source_root"

# Select the archive's pinned toolchain explicitly. Sweeping RUSTUP_TOOLCHAIN
# removes the caller's environment override, but a directory override recorded in
# rustup's settings still outranks rust-toolchain.toml for every bare rustc and
# cargo call, and a custom toolchain reached that way can report the pinned
# version while being a different compiler. Setting RUSTUP_TOOLCHAIN from the
# archive's own pin outranks a directory override in turn, and leaves the recorded
# commands unchanged. Confirm the selection resolves inside this account's rustup
# toolchain directory for the pinned version.
toolchain_pin=$(awk -F'"' '/^[[:space:]]*channel[[:space:]]*=/ { print $2; exit }' rust-toolchain.toml)
if [[ ! $toolchain_pin =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
    echo "archive must pin an exact numeric toolchain; found '${toolchain_pin:-none}'" >&2
    exit 2
fi
export RUSTUP_TOOLCHAIN="$toolchain_pin"
toolchain_prefix="$rustup_home/toolchains/$toolchain_pin-"
resolved_rustc_binary=$("$rustup_exe" which rustc)
resolved_cargo_binary=$("$rustup_exe" which cargo)
if [[ $resolved_rustc_binary != "$toolchain_prefix"* ]]; then
    echo "rustc resolves to $resolved_rustc_binary, outside $toolchain_prefix*" >&2
    exit 2
fi
if [[ $resolved_cargo_binary != "$toolchain_prefix"* ]]; then
    echo "cargo resolves to $resolved_cargo_binary, outside $toolchain_prefix*" >&2
    exit 2
fi
resolved_rustc_version=$("$resolved_rustc_binary" -V | awk '{print $2}')
resolved_cargo_version=$("$resolved_cargo_binary" -V | awk '{print $2}')
resolved_llvm_version=$("$resolved_rustc_binary" -vV | awk -F': ' '/^LLVM version:/ { print $2; exit }')
if [[ ! $resolved_llvm_version =~ ^[0-9]+(\.[0-9]+)*$ ]]; then
    echo "rustc reports no usable LLVM version: '${resolved_llvm_version:-none}'" >&2
    exit 2
fi
if [[ $resolved_rustc_version != "$toolchain_pin" ]]; then
    echo "rustc $resolved_rustc_version does not match pinned $toolchain_pin" >&2
    exit 2
fi
if [[ $resolved_cargo_version != "$toolchain_pin" ]]; then
    echo "cargo $resolved_cargo_version does not match pinned $toolchain_pin" >&2
    exit 2
fi

{
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'archive_embedded_commit=%s\n' "$archive_embedded_commit"
    printf 'runner_sha256='; sha256sum "$experiment_dir/run_host.sh" | awk '{print $1}'
    printf 'toolchain_pin=%s\n' "$toolchain_pin"
    printf 'toolchain_selection=RUSTUP_TOOLCHAIN=%s\n' "$toolchain_pin"
    printf 'resolved_rustc_version=%s\n' "$resolved_rustc_version"
    printf 'resolved_cargo_version=%s\n' "$resolved_cargo_version"
    printf 'resolved_llvm_version=%s\n' "$resolved_llvm_version"
    printf 'resolved_rustc_binary=%s\n' "$resolved_rustc_binary"
    printf 'resolved_cargo_binary=%s\n' "$resolved_cargo_binary"
    printf 'account_home=%s\n' "$account_home"
    printf 'rustup_home=%s\n' "$rustup_home"
    printf 'command_path=%s\n' "$PATH"
    printf 'cargo_home_isolated=yes\n'
    printf 'swept_environment_names=%s\n' "${swept_environment_names[*]:-none}"
} >"$output_dir/source-identity.txt"

cpu_model=$(lscpu | awk -F: '/^Model name:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }')
if [[ -z $cpu_model ]]; then
    cpu_model=$(lscpu | awk -F: '/^Model:/ { sub(/^[[:space:]]+/, "", $2); print $2; exit }')
fi
{
    printf 'date_utc='; date -u +%Y-%m-%dT%H:%M:%SZ
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'hostname_short='; hostname
    printf 'hostname_fqdn=%s\n' "$resolved_hostname"
    printf 'uname_all='; uname -a
    printf 'architecture=%s\n' "$architecture"
    printf 'kernel='; uname -r
    printf 'cpu_model=%s\n' "${cpu_model:-unavailable}"
    printf 'cpu_count_online='; getconf _NPROCESSORS_ONLN
    printf 'cpu_count_available='; nproc
    printf 'build_flags=--release -C opt-level=3 -C target-cpu=native -C panic=abort\n'
    printf 'measurement_kind=deterministic correctness and codegen only\n'
    printf 'fresh_process_runs=8\n'
    printf 'timing_reported=no\n'
    printf 'lscpu_begin\n'
    lscpu
    printf 'lscpu_end\n'
} >"$output_dir/host.txt" 2>&1

run_record proc-cpuinfo.txt sed -n '1,320p' /proc/cpuinfo
run_record rustc-version.txt "$resolved_rustc_binary" -vV
run_record cargo-version.txt "$resolved_cargo_binary" -Vv
run_record python-version.txt python3 -VV
run_record git-version.txt git --version
run_record objdump-version.txt objdump --version
run_record readelf-version.txt readelf --version
run_record rust-target-cfg.txt "$resolved_rustc_binary" --print cfg
run_record rust-native-target-cfg.txt "$resolved_rustc_binary" -C target-cpu=native --print cfg
run_record rust-target-features.txt "$resolved_rustc_binary" --print target-features

# A private baseline gives the extracted archive a Git work tree. Scope the
# staged whitespace check to this topic and its lockfile entry: older retained
# disassembly elsewhere in the workspace contains intentional trailing bytes.
# The requested `git diff --check` gate and final check detect later mutations.
git init -q "$source_root"
git -C "$source_root" -c core.attributesFile=/dev/null add --all
run_record source-whitespace-baseline.txt git -C "$source_root" diff --cached --check -- \
    Cargo.lock topics/042-rust-aliasing-provenance
run_record source-baseline-commit.txt git -C "$source_root" \
    -c user.name=topic42-receipt \
    -c user.email=topic42-receipt.invalid \
    -c commit.gpgSign=false \
    -c core.hooksPath=/dev/null \
    commit -q -m exact-source-baseline

gates="$output_dir/gates"
mkdir -m 0700 -- "$gates"
cargo_target="$work_dir/cargo-target"
native_target="$work_dir/native-target"
manifest="$source_root/Cargo.toml"
package=rust-aliasing-provenance

run_record gates/01-git-diff-check.txt git -C "$source_root" diff --check
run_record gates/02-cargo-fmt.txt "$resolved_cargo_binary" fmt --manifest-path "$manifest" --all -- --check
run_record gates/03-cargo-test-lib-examples.txt env CARGO_TARGET_DIR="$cargo_target" \
    "$resolved_cargo_binary" test --manifest-path "$manifest" --locked --offline --workspace --lib --examples
run_record gates/04-cargo-test-doc.txt env CARGO_TARGET_DIR="$cargo_target" \
    "$resolved_cargo_binary" test --manifest-path "$manifest" --locked --offline --workspace --doc
run_record gates/05-cargo-clippy.txt env CARGO_TARGET_DIR="$cargo_target" \
    "$resolved_cargo_binary" clippy --manifest-path "$manifest" --locked --offline --workspace --all-targets -- -D warnings
run_record gates/06-cargo-bench-no-run.txt env CARGO_TARGET_DIR="$cargo_target" \
    "$resolved_cargo_binary" bench --manifest-path "$manifest" --locked --offline --workspace --no-run
run_record gates/07-cargo-doc.txt env CARGO_TARGET_DIR="$cargo_target" RUSTDOCFLAGS='-D warnings' \
    "$resolved_cargo_binary" doc --manifest-path "$manifest" --locked --offline --workspace --no-deps

native_flags='-C opt-level=3 -C target-cpu=native -C panic=abort'
run_record build-native.txt env CARGO_TARGET_DIR="$native_target" RUSTFLAGS="$native_flags" \
    "$resolved_cargo_binary" build -vv --manifest-path "$manifest" --locked --offline --release \
    --package "$package" --example provenance_demo

codegen="$output_dir/codegen"
mkdir -m 0700 -- "$codegen"
run_record codegen-command.txt "$resolved_rustc_binary" \
    --crate-name rust_aliasing_provenance \
    --edition=2024 \
    --crate-type=lib \
    -C opt-level=3 \
    -C target-cpu=native \
    -C panic=abort \
    --emit="llvm-ir=$codegen/topic42.ll,asm=$codegen/topic42.s,obj=$codegen/topic42.o" \
    "$topic_dir/src/lib.rs"

native_binary="$native_target/release/examples/provenance_demo"
expected="$experiment_dir/expected.txt"
run_record run-processes.txt python3 -I -B "$experiment_dir/run_processes.py" \
    --binary "$native_binary" \
    --expected "$expected" \
    --output "$output_dir/processes" \
    --runs 8

# Inspect the digest-bound executable retained by the process runner. LLVM IR
# carries the target-independent alias proof. These native files are retained
# as observations and are not validated by architecture-specific mnemonics.
retained_binary="$output_dir/processes/provenance-demo"
run_record codegen/linked.objdump.txt objdump -drwC "$retained_binary"
run_record codegen/linked.symbols.txt nm -n "$retained_binary"
run_record codegen/linked.elf.txt readelf -h -n -A "$retained_binary"

run_record source-clean-after.txt git -C "$source_root" diff --check
write_source_manifest "$output_dir/source-manifest-after.sha256"
cmp "$output_dir/source-manifest-before.sha256" "$output_dir/source-manifest-after.sha256"
run_record validate-receipts.txt python3 -I -B "$experiment_dir/validate_receipts.py" \
    --root "$output_dir" \
    --expected "$expected" \
    --source-commit "$source_commit" \
    --archive-sha256 "$archive_digest" \
    --expected-hostname "$resolved_hostname" \
    --expected-rustc-version "$toolchain_pin" \
    --expected-llvm-version "$resolved_llvm_version"

# Only retained evidence remains. The deleted path was created by this run and
# is constrained to OUTPUT_DIR/.work under a direct /tmp child.
cd "$output_dir"
rm -rf -- "$work_dir"
{
    printf 'status=PASS\n'
    printf 'source_commit=%s\n' "$source_commit"
    printf 'source_archive_sha256=%s\n' "$archive_digest"
    printf 'ssh_target_label=%s\n' "$SSH_TARGET_LABEL"
    printf 'ssh_resolved_hostname=%s\n' "$SSH_RESOLVED_HOSTNAME"
    printf 'architecture=%s\n' "$architecture"
    printf 'fresh_processes=8\n'
    printf 'timing_reported=no\n'
    printf 'llvm_reference_noalias=yes\n'
    printf 'llvm_reference_source_loads=1\n'
    printf 'llvm_raw_noalias=no\n'
    printf 'llvm_raw_source_loads=2\n'
} >"$output_dir/status.txt"
(
    cd "$output_dir"
    rg --files -g '!bundle-manifest.sha256' -0 |
        LC_ALL=C sort -z |
        xargs -0 sha256sum --
) >"$output_dir/bundle-manifest.sha256"

printf 'experiment_status=PASS output=%s\n' "$output_dir"
