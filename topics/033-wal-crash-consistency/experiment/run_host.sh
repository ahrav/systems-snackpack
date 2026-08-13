#!/usr/bin/env bash
set -Eeuo pipefail

# Bash sources a BASH_ENV hook before this script's first line runs, and the
# hook can unset BASH_ENV, alias or shadow builtins, and mutate any shell
# variable — so no in-shell state can prove the hook's absence. Decide from
# /proc/self/environ instead: the kernel fixes that snapshot at exec time, a
# hook cannot rewrite it, and bash sources BASH_ENV only when the variable
# appears in that startup environment. When it does appear, re-exec once
# through /usr/bin/env -u BASH_ENV and /proc/self/exe (kernel-provided paths;
# "$BASH" is hook-mutable): the re-executed interpreter's environ lacks
# BASH_ENV, so it never sourced a hook, nothing hook-created survives the
# exec, and this branch is not taken again. Inherited loader variables are
# unset with shell builtins first — /usr/bin/env and the interpreter are
# dynamically linked, so an interposed loader would otherwise run inside the
# sanitizing exec itself; the swept names ride through the exec (names only,
# never values) so the evidence record still lists them. Boundary: a hook
# hostile enough to shadow read or exec can sabotage these statements too —
# no in-process check survives that adversary. The defense there is the
# operator contract plus the recorded tool and environment provenance.
bash_env_was_present=0
while IFS= read -r -d '' environ_entry; do
	case $environ_entry in
	BASH_ENV=*) bash_env_was_present=1 ;;
	esac
done </proc/self/environ
if ((bash_env_was_present)); then
	pre_exec_swept=()
	while IFS= read -r variable; do
		case $variable in
		LD_* | DYLD_* | GLIBC_TUNABLES)
			pre_exec_swept+=("$variable")
			unset "$variable"
			;;
		esac
	done < <(compgen -e)
	TOPIC33_PRE_EXEC_SWEPT="${pre_exec_swept[*]}" \
		exec /usr/bin/env -u BASH_ENV /proc/self/exe "$0" "$@"
fi
# Exported functions (BASH_FUNC_* environment entries) arrive without any
# BASH_ENV hook, so this refusal is needed even on the hook-free path.
if [[ -n $(compgen -A function) ]]; then
	echo "exact-source measurement refuses inherited shell functions" >&2
	exit 2
fi

# LD_PRELOAD, LD_AUDIT, and GLIBC_TUNABLES let the host interpose code into
# every dynamically linked tool and probe child, Cargo reads flag variables
# beyond RUSTFLAGS (CARGO_ENCODED_RUSTFLAGS, CARGO_BUILD_RUSTFLAGS), and
# tar/gzip/ripgrep honor TAR_OPTIONS, GZIP, and RIPGREP_CONFIG_PATH, so
# inherited values could build, extract, or gate with unrecorded behavior.
# The sweep runs before any external command, including sort: an interposed
# loader would already run inside the first external process. Swept names are
# recorded into the evidence later; values never are, because swept variables
# include common secrets such as CARGO_ registry tokens.
swept_environment_names=()
# Names of loader variables the pre-exec sweep already removed.
if [[ -n ${TOPIC33_PRE_EXEC_SWEPT:-} ]]; then
	read -r -a swept_environment_names <<<"$TOPIC33_PRE_EXEC_SWEPT"
fi
unset TOPIC33_PRE_EXEC_SWEPT
while IFS= read -r variable; do
	case $variable in
	RUSTUP_HOME) ;;
	LD_* | DYLD_* | GLIBC_TUNABLES | MALLOC_* | \
		AR | ARFLAGS | AS | CC | CFLAGS | COMPILER_PATH | CPP | CPPFLAGS | \
		CXX | CXXFLAGS | GCC_EXEC_PREFIX | LD | LDFLAGS | LIBRARY_PATH | \
		CPATH | C_INCLUDE_PATH | CPLUS_INCLUDE_PATH | MAKEFLAGS | NM | \
		OBJCOPY | OBJDUMP | PKG_CONFIG | PKG_CONFIG_PATH | RANLIB | \
		RIPGREP_CONFIG_PATH | STRIP | TAR_OPTIONS | GZIP | PYTHON* | \
		VIRTUAL_ENV | CLIPPY_CONF_DIR | CARGO_* | GIT_* | RUST*)
		swept_environment_names+=("$variable")
		unset "$variable"
		;;
	esac
done < <(compgen -e)
if [[ -s /etc/ld.so.preload ]]; then
	echo "exact-source measurement refuses /etc/ld.so.preload interposition" >&2
	exit 2
fi

# Bind required commands to absolute paths before use so PATH cannot select
# different executables between the presence check and the call, and so the
# recorded toolchain identities come from the same binaries the gates run.
required_tools=(
	awk bash cargo cc cmp cp date dirname env find findmnt getconf git gzip
	hostname lsblk lscpu mkdir mktemp mv nm objdump python3 realpath rg rm
	rustc rustdoc sed sha256sum sort tar touch uname xargs cargo-clippy
	cargo-fmt
)
declare -A tool_paths
for tool in "${required_tools[@]}"; do
	if ! tool_path=$(type -P "$tool"); then
		echo "required tool is absent from PATH: $tool" >&2
		exit 2
	fi
	if [[ $tool_path != /* ]]; then
		echo "required tool did not resolve to an absolute path: $tool_path" >&2
		exit 2
	fi
	tool_paths[$tool]=$tool_path
	hash -p "$tool_path" "$tool"
done
readonly PATH

if [[ $# -ne 5 ]]; then
	echo "usage: run_host.sh SOURCE.tar.gz OUTPUT HOST_LABEL SOURCE_COMMIT EXPECTED_ARCHIVE_SHA256" >&2
	exit 2
fi

source_archive=$(realpath "$1")
output=$(realpath -m "$2")
host_label=$3
source_commit=$4
expected_archive_sha256=$5
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
build_root=
cargo_home=
run_completed=0

seal_evidence() {
	(
		cd "$output"
		manifest=.SHA256SUMS.tmp
		rm -f "$manifest"
		find . -type f ! -name SHA256SUMS ! -name "$manifest" -print0 |
			LC_ALL=C sort -z |
			xargs -0 sha256sum >"$manifest"
		mv "$manifest" SHA256SUMS
		sha256sum --check --quiet SHA256SUMS
	)
}

write_status() {
	local status=$1
	local exit_code=$2
	{
		echo "status=$status"
		echo "exit_code=$exit_code"
		echo "run_started_utc=$run_started_utc"
		echo "run_finished_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
		printf 'host_label=%q\n' "$host_label"
		echo "source_commit=$source_commit"
		echo "source_archive_sha256=$expected_archive_sha256"
	} >"$output/run.status"
}

finalize() {
	local exit_code=$?
	trap - EXIT
	set +e
	if [[ -n $cargo_home && -f $cargo_home/.topic33-cargo-home ]]; then
		rm -rf "$cargo_home"
	fi
	if [[ -n $build_root && -f $build_root/.topic33-build-root ]]; then
		rm -rf "$build_root"
	fi
	if [[ -d $output ]]; then
		if ((exit_code == 0 && run_completed == 1)); then
			write_status success 0
		else
			((exit_code == 0)) && exit_code=1
			write_status failed "$exit_code"
		fi
		if ! seal_evidence; then
			exit_code=1
			write_status failed 1
			printf 'failure_reason=evidence_seal_failed\n' >>"$output/run.status"
			seal_evidence || true
		fi
	fi
	exit "$exit_code"
}

if [[ $(uname -s) != Linux ]]; then
	echo "run_host.sh requires Linux" >&2
	exit 2
fi
if [[ ! -f $source_archive ]]; then
	echo "source archive is absent: $source_archive" >&2
	exit 2
fi
if [[ -e $output ]]; then
	echo "output already exists: $output" >&2
	exit 2
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
	echo "source commit must be 40 lowercase hexadecimal characters" >&2
	exit 2
fi
if [[ ! $expected_archive_sha256 =~ ^[0-9a-f]{64}$ ]]; then
	echo "archive digest must be 64 lowercase hexadecimal characters" >&2
	exit 2
fi
if [[ -z $host_label || $host_label == *$'\n'* || $host_label == *$'\r'* ]]; then
	echo "host label must be non-empty and single-line" >&2
	exit 2
fi

# Copy the archive into the private build root first, then verify and extract
# only the copy: verifying the caller's path and extracting it later would let
# a replacement between the checks and the extraction build unverified bytes
# while the receipts record the earlier digest.
build_root=$(mktemp -d "${TMPDIR:-/tmp}/topic33-build-root.XXXXXXXX")
touch "$build_root/.topic33-build-root"
verified_archive="$build_root/source.tar.gz"
if ! cp "$source_archive" "$verified_archive"; then
	rm -rf "$build_root"
	echo "could not copy source archive into the build root" >&2
	exit 2
fi
actual_archive_sha256=$(sha256sum "$verified_archive" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$expected_archive_sha256" ]]; then
	rm -rf "$build_root"
	echo "source archive digest mismatch" >&2
	exit 2
fi
archive_commit=$(git get-tar-commit-id < <(gzip -dc "$verified_archive"))
if [[ $archive_commit != "$source_commit" ]]; then
	rm -rf "$build_root"
	echo "Git archive commit $archive_commit does not match $source_commit" >&2
	exit 2
fi

mkdir -p "$output/gates"
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Only names for swept variables: this file is sealed into the promoted
# evidence archive and swept values include common secrets. The policy lines
# record the full sweep pattern; the unset lines record which of those
# variables this host actually had set.
{
	echo "swept_prefix_globs=CARGO_* GIT_* RUST* LD_* DYLD_* MALLOC_* PYTHON*"
	echo "swept_exact_names=GLIBC_TUNABLES VIRTUAL_ENV RIPGREP_CONFIG_PATH TAR_OPTIONS GZIP CLIPPY_CONF_DIR AR ARFLAGS AS CC CFLAGS COMPILER_PATH CPP CPPFLAGS CXX CXXFLAGS GCC_EXEC_PREFIX LD LDFLAGS LIBRARY_PATH CPATH C_INCLUDE_PATH CPLUS_INCLUDE_PATH MAKEFLAGS NM OBJCOPY OBJDUMP PKG_CONFIG PKG_CONFIG_PATH RANLIB STRIP"
	echo "kept_names=RUSTUP_HOME"
	for variable_name in "${swept_environment_names[@]}"; do
		printf 'unset %s\n' "$variable_name"
	done
	if [[ -n ${RUSTUP_HOME:-} ]]; then
		printf 'kept RUSTUP_HOME=%q\n' "$RUSTUP_HOME"
	fi
} >"$output/environment.before.txt"

{
	printf 'bash_path=%q\nbash_version=%q\nPATH=%q\n' \
		"$BASH" "$BASH_VERSION" "$PATH"
	resolved_bash_path=$(realpath "$BASH")
	printf 'bash_resolved_path=%q\nbash_sha256=%s\n' \
		"$resolved_bash_path" \
		"$(sha256sum "$resolved_bash_path" | awk '{print $1}')"
	for tool in "${required_tools[@]}"; do
		tool_path=${tool_paths[$tool]}
		resolved_tool_path=$(realpath "$tool_path")
		tool_sha256=$(sha256sum "$resolved_tool_path" | awk '{print $1}')
		printf '%s_path=%q\n%s_resolved_path=%q\n%s_sha256=%s\n' \
			"$tool" "$tool_path" "$tool" "$resolved_tool_path" \
			"$tool" "$tool_sha256"
	done
} >"$output/tool-provenance.txt"

tar -xzf "$verified_archive" -C "$build_root"
topic="$build_root/topics/033-wal-crash-consistency"
if [[ ! -d $topic ]]; then
	echo "Topic 33 source is absent from archive" >&2
	exit 2
fi

# Cargo reads .cargo/config.toml from the working directory and every
# ancestor before $CARGO_HOME, and rustfmt and Clippy likewise discover
# rustfmt.toml and clippy.toml in ancestor directories, so a config above the
# caller-controlled TMPDIR could add rustflags, a rustc wrapper, source
# replacement, or lint and format rules that no recorded input names.
config_scan_directory=$build_root
while :; do
	for ambient_config in \
		"$config_scan_directory/.cargo/config.toml" \
		"$config_scan_directory/.cargo/config" \
		"$config_scan_directory/rustfmt.toml" \
		"$config_scan_directory/.rustfmt.toml" \
		"$config_scan_directory/clippy.toml" \
		"$config_scan_directory/.clippy.toml"; do
		if [[ -e $ambient_config ]]; then
			echo "unrecorded toolchain config would alter gates: $ambient_config" >&2
			exit 2
		fi
	done
	if [[ $config_scan_directory == / ]]; then
		break
	fi
	config_scan_directory=$(dirname "$config_scan_directory")
done

pinned_toolchain=$(sed -n 's/^channel = "\(.*\)"$/\1/p' "$build_root/rust-toolchain.toml")
if [[ -z $pinned_toolchain ]]; then
	echo "could not parse pinned Rust toolchain" >&2
	exit 2
fi
export RUSTUP_TOOLCHAIN="$pinned_toolchain"
resolved_rustc=$(rustc --version | awk '{print $2}')
if [[ $resolved_rustc != "$pinned_toolchain" ]]; then
	echo "resolved rustc $resolved_rustc does not match $pinned_toolchain" >&2
	exit 2
fi
# The bound rustc/cargo paths are rustup proxies, so their hashes do not
# identify the compiler rustup dispatches to; an ambient RUSTUP_HOME could
# supply an unrecorded toolchain that reports the pinned version. Record the
# dispatched binaries and check the version against the dispatched compiler.
{
	if rustup_path=$(type -P rustup); then
		printf 'rustup_path=%q\nrustup_sha256=%s\n' \
			"$rustup_path" \
			"$(sha256sum "$(realpath "$rustup_path")" | awk '{print $1}')"
		for component in rustc cargo rustdoc cargo-fmt cargo-clippy; do
			dispatched_path=$(rustup which "$component")
			resolved_dispatched_path=$(realpath "$dispatched_path")
			printf '%s_dispatched_path=%q\n%s_dispatched_sha256=%s\n' \
				"$component" "$resolved_dispatched_path" \
				"$component" \
				"$(sha256sum "$resolved_dispatched_path" | awk '{print $1}')"
			if [[ $component == rustc ]]; then
				dispatched_rustc_path=$resolved_dispatched_path
			fi
			# Cargo resolves rustdoc from PATH unless RUSTDOC names it, so
			# pin the doc gates to the hashed component.
			if [[ $component == rustdoc ]]; then
				export RUSTDOC="$resolved_dispatched_path"
			fi
		done
		dispatched_rustc_version=$("$dispatched_rustc_path" --version | awk '{print $2}')
		printf 'rustc_dispatched_version=%q\n' "$dispatched_rustc_version"
		if [[ $dispatched_rustc_version != "$pinned_toolchain" ]]; then
			echo "dispatched rustc $dispatched_rustc_version does not match $pinned_toolchain" >&2
			exit 2
		fi
	else
		echo "rustup_path=absent"
		echo "rustc_dispatch=direct"
	fi
} >"$output/toolchain-dispatch.txt"

cargo_home=$(mktemp -d "${TMPDIR:-/tmp}/topic33-cargo-home.XXXXXXXX")
touch "$cargo_home/.topic33-cargo-home"
export CARGO_HOME="$cargo_home"
export CARGO_NET_OFFLINE=true

{
	echo "source_commit=$source_commit"
	echo "source_archive_sha256=$actual_archive_sha256"
	printf 'host_label=%q\n' "$host_label"
} >"$output/source-identity.txt"
{
	printf 'host_label=%q\n' "$host_label"
	# Informational probes must not abort the run under set -e; a restricted
	# host may lack an FQDN or block device visibility. Toolchain identity
	# stays unguarded because a run without it is not valid evidence.
	hostname -f || true
	uname -a
	uname -m
	uname -r
	getconf _NPROCESSORS_ONLN || true
	lscpu || true
	rustc -vV
	cargo -V
	cc --version
	objdump --version
	rustc --print cfg
	rustc -C target-cpu=native --print cfg
	findmnt -T "$output" || true
	findmnt -T "$output" -n -o SOURCE,FSTYPE,OPTIONS || true
	lsblk -o NAME,TYPE,SIZE,ROTA,MODEL,FSTYPE,MOUNTPOINTS || true
} >"$output/host.txt" 2>&1
# Fail closed: an unreadable or empty filesystem type must refuse the run, not
# skip the tmpfs check.
output_fstype=$(findmnt -T "$output" -n -o FSTYPE || true)
if [[ -z $output_fstype ]]; then
	echo "could not determine the filesystem type for $output" >&2
	exit 2
fi
if [[ $output_fstype == tmpfs ]]; then
	echo "measurement output and WAL data must not use tmpfs" >&2
	exit 2
fi
{
	echo "generic: RUSTFLAGS unset"
	echo "native: RUSTFLAGS=-C target-cpu=native"
	echo "workspace gates: RUSTFLAGS unset"
	echo "benchmark: 8 blocks, 4 ABBA and 4 BAAB, 32 fresh processes"
	echo "timed region: record writes plus fdatasync only"
	printf 'output_fstype=%q\n' "$output_fstype"
} >"$output/build-and-run-flags.txt"

source_manifest() {
	(
		cd "$build_root"
		# The verified archive copy sits beside the extracted tree; the
		# manifest covers only the extracted source bytes.
		find . -type f ! -path './target/*' ! -name .topic33-build-root \
			! -path ./source.tar.gz -print0 |
			LC_ALL=C sort -z |
			xargs -0 sha256sum
	)
}
source_manifest >"$output/source-files.before.sha256"

run_gate() {
	local name=$1
	shift
	(cd "$build_root" && "$@") >"$output/gates/$name.log" 2>&1
}

run_gate cargo-fmt cargo fmt --all -- --check
# The top-of-script sweep already cleared RUSTFLAGS and every other Cargo flag
# variable, so the generic build runs with the recorded generic flags.
run_gate cargo-test-package-generic cargo test --locked --package topic-033-wal-crash-consistency
run_gate cargo-build-package-generic cargo build --locked --release \
	--package topic-033-wal-crash-consistency --bin wal-crash-probe
generic_binary="$build_root/target/release/wal-crash-probe"
cp "$generic_binary" "$output/wal-crash-probe.generic"
sha256sum "$output/wal-crash-probe.generic" >"$output/binary.generic.sha256"
"$generic_binary" model >"$output/model.generic.log" 2>&1
"$generic_binary" process-crash "$output/wal-data/generic-crash" \
	>"$output/process-crash.generic.log" 2>&1

export RUSTFLAGS="-C target-cpu=native"
run_gate cargo-test-package-native cargo test --locked --package topic-033-wal-crash-consistency
run_gate cargo-build-package-native cargo build --locked --release \
	--package topic-033-wal-crash-consistency --bin wal-crash-probe
native_binary="$build_root/target/release/wal-crash-probe"
cp "$native_binary" "$output/wal-crash-probe.native"
sha256sum "$output/wal-crash-probe.native" >"$output/binary.native.sha256"
nm -n "$output/wal-crash-probe.native" >"$output/binary.symbols.txt"
rg --no-config -q '[[:space:]][Tt][[:space:]]topic33_crc32c$' "$output/binary.symbols.txt"
objdump -d --no-show-raw-insn --disassemble=topic33_crc32c \
	"$output/wal-crash-probe.native" >"$output/codegen.txt" 2>&1
rg --no-config -q '<topic33_crc32c>:' "$output/codegen.txt"
nm -D "$output/wal-crash-probe.native" >"$output/binary.dynamic-symbols.txt" 2>&1 || true
"$native_binary" model >"$output/model.native.log" 2>&1
"$native_binary" process-crash "$output/wal-data/native-crash" \
	>"$output/process-crash.native.log" 2>&1
"$native_binary" bench-run "$output/wal-data/native-bench" \
	"$output/benchmark.csv" 8 128 256 1 8 330033 \
	>"$output/benchmark-run.log" 2>&1
# -I isolates argv[0] path injection and user site-packages but still imports
# site; -S suppresses sitecustomize and .pth hooks that could patch the
# validator's interpreter.
python3 -I -S "$topic/experiment/validate_receipts.py" \
	"$output/benchmark.csv" "$output/benchmark-summary.json" \
	>"$output/benchmark-validation.log" 2>&1

unset RUSTFLAGS
run_gate cargo-test-lib-bins-examples cargo test --locked --workspace --lib --bins --examples
run_gate cargo-test-doc cargo test --locked --workspace --doc
run_gate cargo-clippy cargo clippy --locked --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --locked --workspace --no-run
run_gate cargo-doc env "RUSTDOCFLAGS=-D warnings" cargo doc --locked --workspace --no-deps

source_manifest >"$output/source-files.after.sha256"
cmp "$output/source-files.before.sha256" "$output/source-files.after.sha256"
run_completed=1
echo "host run: PASS"
