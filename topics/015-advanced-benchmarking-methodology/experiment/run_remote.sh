#!/usr/bin/env bash
set -euo pipefail

if (($# < 2 || $# > 3)); then
    printf 'usage: %s REPOSITORY_ROOT OUTPUT_DIRECTORY [CPU]\n' "$0" >&2
    exit 2
fi

repo_root="$(cd -- "$1" && pwd -P)"
output_dir="$2"
topic_rel="topics/015-advanced-benchmarking-methodology"
topic_dir="$repo_root/$topic_rel"
# The runner's fallback to the first allowed CPU depends on the argument being
# absent, so an omitted CPU must stay omitted rather than become an explicit 0.
if (($# >= 3)); then
    cpu_args=("$3")
    cpu_requested="$3"
else
    cpu_args=()
    cpu_requested="default"
fi

# evidence.sha256 authenticates every file it finds under the output directory,
# so a pre-existing file this run does not overwrite would be signed as though
# it belonged to this collection. Require a dedicated, empty destination.
if [[ -e "$output_dir" ]]; then
    if [[ ! -d "$output_dir" ]]; then
        printf 'OUTPUT_DIRECTORY exists and is not a directory: %s\n' "$output_dir" >&2
        exit 2
    fi
    if [[ -n "$(ls -A -- "$output_dir")" ]]; then
        printf 'OUTPUT_DIRECTORY must be empty; evidence.sha256 would authenticate its existing files: %s\n' \
            "$output_dir" >&2
        exit 2
    fi
fi
mkdir -p "$output_dir"
# Physical resolution on both sides: a logical path can point through a symlink
# into the repository, which the prefix comparison below would then accept.
output_dir="$(cd -- "$output_dir" && pwd -P)"
gates_dir="$output_dir/gates"
mkdir -p "$gates_dir"

# The source manifest scans the topic tree, and the shell creates a redirection
# target before the command it redirects runs. An output directory inside the
# repository would therefore hash generated evidence as source input and record
# a checksum for the manifest itself that is stale the moment it is written.
# Evidence is collected outside the repository and copied in afterwards.
if [[ "$output_dir" == "$repo_root" || "$output_dir" == "$repo_root"/* ]]; then
    printf 'OUTPUT_DIRECTORY must be outside the repository: %s\n' "$output_dir" >&2
    exit 2
fi

# The focused build goes to a private directory so the measured artifact is
# never a stale binary from an earlier build and never disappears into a
# caller-configured target directory. It must also stay outside the output tree:
# evidence.sha256 walks that tree, and the exit trap would delete the Cargo
# artifacts the walk had just hashed.
build_dir="$(cd -- "$(mktemp -d)" && pwd -P)"
trap 'rm -rf -- "$build_dir"' EXIT
if [[ "$build_dir" == "$output_dir" || "$build_dir" == "$output_dir"/* ]]; then
    printf 'temporary build directory %s falls inside OUTPUT_DIRECTORY %s; set TMPDIR elsewhere\n' \
        "$build_dir" "$output_dir" >&2
    exit 2
fi

# The recorded `rustc -vV` provenance and flags only describe the build when no
# environment variable redirects the compiler, wrapper, flags, profile, target
# overrides, or incremental mode. Enumerating dangerous names loses to Cargo's
# namespace (CARGO_BUILD_*, CARGO_PROFILE_*, CARGO_TARGET_<TRIPLE>_*,
# CARGO_ENCODED_*, and additions), so sweep every exported
# CARGO_*/RUSTC*/RUSTDOC*/RUSTFLAGS variable before probing, gating, or
# building, and re-export only the recorded values. CARGO_HOME survives because
# it locates the registry cache, and any Cargo configuration file it finds is
# hashed into the source manifest. RUSTUP_* survives so the build resolves the
# same toolchain the probe records.
swept_variables=()
while IFS= read -r swept_variable; do
    if [[ $swept_variable != CARGO_HOME ]]; then
        swept_variables+=("$swept_variable")
        unset "$swept_variable"
    fi
done < <(compgen -e | rg '^(CARGO_|RUSTC|RUSTDOC|RUSTFLAGS)' || true)

# Cargo discovers configuration hierarchically from the invocation directory up
# through its parents and from CARGO_HOME, and TOML admits section, dotted, and
# inline spellings for `build.rustc*`, `profile.*`, and `target.*` overrides. A
# discoverable file can therefore redirect the compiler, wrapper, linker, target,
# or profile in a way no pattern scan can whitelist, so any such file is an
# unrecorded build input. The builds run from repo_root, so that is where
# discovery starts.
cargo_config_candidates=(
    "${CARGO_HOME:-$HOME/.cargo}/config.toml"
    "${CARGO_HOME:-$HOME/.cargo}/config"
)
config_scan_dir=$repo_root
while :; do
    cargo_config_candidates+=(
        "$config_scan_dir/.cargo/config.toml"
        "$config_scan_dir/.cargo/config"
    )
    if [[ $config_scan_dir == / ]]; then
        break
    fi
    config_scan_dir=$(dirname -- "$config_scan_dir")
done
for cargo_config in "${cargo_config_candidates[@]}"; do
    if [[ -f $cargo_config ]]; then
        printf 'Cargo configuration is an unrecorded build input: %s\n' "$cargo_config" >&2
        exit 2
    fi
done

# A caller-declared source identity that nothing checks can attribute the
# measured binary to source it did not come from. Derive the commit where it is
# derivable, refuse a declaration that disagrees, and refuse a dirty tree
# because no commit describes it. The archive digest stays declared: the archive
# is not present here to hash.
if git -C "$repo_root" rev-parse --git-dir >/dev/null 2>&1; then
    source_commit="$(git -C "$repo_root" rev-parse HEAD)"
    if [[ -n "${SOURCE_COMMIT:-}" ]]; then
        declared_commit="$(
            git -C "$repo_root" rev-parse --verify --quiet "${SOURCE_COMMIT}^{commit}" || true
        )"
        if [[ "$declared_commit" != "$source_commit" ]]; then
            printf 'SOURCE_COMMIT %s does not name the checked-out commit %s\n' \
                "${SOURCE_COMMIT}" "$source_commit" >&2
            exit 2
        fi
    fi
    if [[ -n "$(git -C "$repo_root" status --porcelain)" ]]; then
        printf 'the checkout at %s has uncommitted changes; no commit describes the measured source\n' \
            "$repo_root" >&2
        exit 2
    fi
    source_commit_verification="git-checkout"
else
    if [[ -z "${SOURCE_COMMIT:-}" ]]; then
        printf 'SOURCE_COMMIT is required because %s is not a git checkout\n' "$repo_root" >&2
        exit 2
    fi
    source_commit="${SOURCE_COMMIT}"
    source_commit_verification="declared"
fi

if ! command -v taskset >/dev/null 2>&1; then
    printf 'taskset is required for remote evidence collection\n' >&2
    exit 2
fi

# The captured host record must not leak the machine identity into shared
# evidence; every occurrence of the local hostname is replaced before writing.
host_name="$(uname -n)"
(
    # The toolchain probes run from the repository so they observe the same
    # rust-toolchain.toml override every build below uses. Probing from the
    # caller's directory would attribute the measured binary to whichever
    # toolchain the caller defaults to.
    cd "$repo_root"
    date -u '+utc=%Y-%m-%dT%H:%M:%SZ'
    uname -a
    printf 'architecture=%s\n' "$(uname -m)"
    printf 'kernel=%s\n' "$(uname -r)"
    printf 'online_cpus=%s\n' "$(getconf _NPROCESSORS_ONLN)"
    lscpu
    rustc -vV
    cargo -V
    cc --version
    rustc --print cfg -C target-cpu=native
) 2>&1 | sed "s/${host_name}/redacted-host/g" >"$output_dir/host.txt"

# One definition feeds both the provenance record and the build so the
# recorded flags cannot diverge from the flags the measured binary used.
native_rustflags="-C target-cpu=native -C codegen-units=1"

printf '%s\n' \
    "workspace_gates=compiler defaults" \
    "focused_build=--release ${native_rustflags}" \
    "swept_build_environment=${swept_variables[*]:-none}" \
    "focused_affinity_requested=taskset -c ${cpu_requested}" \
    "source_commit=${source_commit}" \
    "source_commit_verification=${source_commit_verification}" \
    "source_archive_sha256=${SOURCE_ARCHIVE_SHA256:-unknown}" \
    "source_archive_verification=declared" \
    >"$output_dir/build-flags.txt"

# The measured binary is determined by more than the topic directory: the
# package inherits edition, rust-version, and lints from the root manifest, the
# lockfile pins the dependency graph, the toolchain file pins the compiler, and
# Cargo configuration can inject build flags. Hashing only the topic would let
# an identical manifest accompany a differently built binary.
(
    cd "$repo_root"
    {
        rg --files "$topic_rel"
        for input in \
            Cargo.toml \
            Cargo.lock \
            rust-toolchain.toml \
            rust-toolchain \
            .cargo/config.toml \
            .cargo/config; do
            if [[ -f "$input" ]]; then
                printf '%s\n' "$input"
            fi
        done
    } | sort -u | xargs sha256sum
) >"$output_dir/source-files.sha256"

(
    cd "$repo_root"
    cargo fmt --all -- --check
) >"$gates_dir/cargo-fmt.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --lib --examples
) >"$gates_dir/cargo-test-lib-examples.log" 2>&1
(
    cd "$repo_root"
    cargo test --workspace --doc
) >"$gates_dir/cargo-test-doc.log" 2>&1
(
    cd "$repo_root"
    cargo clippy --workspace --all-targets -- -D warnings
) >"$gates_dir/cargo-clippy.log" 2>&1
(
    cd "$repo_root"
    cargo bench --workspace --no-run
) >"$gates_dir/cargo-bench-no-run.log" 2>&1
(
    cd "$repo_root"
    RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
) >"$gates_dir/cargo-doc.log" 2>&1

(
    cd "$repo_root"
    RUSTFLAGS="$native_rustflags" \
        cargo build --release \
        --target-dir "$build_dir" \
        -p advanced-benchmarking-methodology \
        --example order_bias
) >"$output_dir/native-build.log" 2>&1

# --target-dir outranks both CARGO_TARGET_DIR and build.target-dir, so this path
# is the artifact Cargo just emitted rather than whatever the repository's
# default target directory happens to hold.
binary="$build_dir/release/examples/order_bias"
if [[ ! -x "$binary" ]]; then
    printf 'focused build did not produce %s\n' "$binary" >&2
    exit 1
fi
# The digest is recorded against the artifact name because the build directory
# is ephemeral; including its path would make identical binaries produce
# different-looking evidence between runs.
(cd -- "$(dirname -- "$binary")" && sha256sum "$(basename -- "$binary")") \
    >"$output_dir/order_bias.sha256"
nm -C "$binary" >"$output_dir/order_bias.symbols.txt"

"$topic_dir/experiment/run_processes.sh" \
    "$binary" \
    "$output_dir/raw.csv" \
    "$output_dir/summary.csv" \
    12 \
    "${cpu_args[@]+"${cpu_args[@]}"}" \
    >"$output_dir/process.log" 2>&1

# The runner resolves and probes its own CPU, so the branch it reports is the
# only record of the affinity that actually applied. Affinity is part of this
# evidence claim, so an unpinned run is a failed collection, not a footnote.
resolved_affinity="$(sed -n 's/^affinity=//p' "$output_dir/process.log" | tail -1)"
if [[ -z "$resolved_affinity" ]]; then
    printf 'run_processes.sh did not report an affinity branch\n' >&2
    exit 1
fi
if [[ "$resolved_affinity" == "none" ]]; then
    printf 'affinity is required for this evidence run; runner reported none\n' >&2
    exit 1
fi
printf 'focused_affinity_actual=%s\n' "$resolved_affinity" \
    >"$output_dir/affinity-resolved.txt"

# objdump prints the path it was given as a header, so it is invoked the same
# way as sha256sum above: from the build directory with a bare artifact name.
# That keeps the ephemeral build path out of retained code-generation evidence.
(cd -- "$(dirname -- "$binary")" && objdump -d -C "$(basename -- "$binary")") \
    >"$output_dir/codegen-full.txt"
rg -n -C 16 "advanced_benchmarking_methodology::checksum" \
    "$output_dir/codegen-full.txt" \
    >"$output_dir/codegen-checksum.txt"
gzip -9 "$output_dir/codegen-full.txt"

(
    cd "$output_dir"
    rg --files . |
        sort |
        rg -v '^\./evidence\.sha256$' |
        xargs sha256sum
) >"$output_dir/evidence.sha256"
