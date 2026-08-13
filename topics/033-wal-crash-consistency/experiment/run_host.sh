#!/bin/bash -p
set -Eeuo pipefail

# Privileged mode (-p) is the structural guard: bash started with -p neither
# imports exported functions (BASH_FUNC_*) nor sources a BASH_ENV hook, and
# it ignores inherited SHELLOPTS/BASHOPTS, so nothing attacker-supplied runs
# or shadows a builtin before this script's first line. Direct execution gets
# -p from the shebang. When the script is started as `bash run_host.sh`, the
# shebang is bypassed and a hook or imported function may already be live —
# and could in principle shadow the very statements below; that residue is
# unavoidable in-process and is covered by the operator contract plus the
# recorded provenance. The recovery path re-execs once into a privileged
# interpreter through fixed root-owned paths (/usr/bin/env and /bin/bash,
# the shebang interpreter; "$BASH" is hook-mutable, and /proc/self/exe
# cannot name the shell here because env resolves it after the first exec,
# when it points at env itself), scrubbing BASH_ENV and every BASH_FUNC_*
# entry named by the kernel's environ snapshot so child processes never see
# them either. The re-exec also fires from a privileged shell whose
# environment still carries those entries, so gates and probes inherit a
# clean environment. Code-injecting loader variables (LD_PRELOAD, LD_AUDIT,
# LD_LIBRARY_PATH) refuse the run outright before the re-exec — the loader
# already applied them to this interpreter. The remaining inherited loader
# variables are unset with shell builtins before the exec — /usr/bin/env and
# the interpreter are dynamically linked, so leftover loader state would
# otherwise act inside the sanitizing exec itself; the swept names ride
# through the exec (names only, never values) so the evidence record still
# lists them.
env_scrub_args=()
loader_interposition_names=()
while IFS= read -r -d '' environ_entry; do
	case $environ_entry in
	BASH_ENV=* | BASH_FUNC_*%%=*)
		env_scrub_args+=(-u "${environ_entry%%=*}")
		;;
	# These load or substitute code inside every dynamically linked process
	# — including the interpreter running this line, which the loader
	# already processed before the script started. No in-process unset can
	# undo that, so their presence at startup refuses the run below.
	LD_PRELOAD=* | LD_AUDIT=* | LD_LIBRARY_PATH=*)
		loader_interposition_names+=("${environ_entry%%=*}")
		;;
	esac
done </proc/self/environ
if ((${#loader_interposition_names[@]} > 0)); then
	echo "exact-source measurement refuses loader interposition variables set at startup: ${loader_interposition_names[*]}" >&2
	echo "start from a clean environment (e.g. env -u LD_PRELOAD -u LD_AUDIT -u LD_LIBRARY_PATH ...)" >&2
	exit 2
fi
if [[ $- != *p* ]] || ((${#env_scrub_args[@]} > 0)); then
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
		exec /usr/bin/env ${env_scrub_args[@]+"${env_scrub_args[@]}"} \
		/bin/bash -p "$0" "$@"
fi
# Backstop only: privileged mode already refuses function import.
if [[ -n $(compgen -A function) ]]; then
	echo "exact-source measurement refuses inherited shell functions" >&2
	exit 2
fi

# LD_PRELOAD, LD_AUDIT, and LD_LIBRARY_PATH refuse the run at startup above
# — the loader applied them to this interpreter before its first line, so
# sweeping them here would only protect children while the sealing process
# itself ran interposed. The remaining inherited variables are swept for the
# children: GLIBC_TUNABLES and MALLOC_* alter libc behavior, Cargo reads flag
# variables beyond RUSTFLAGS (CARGO_ENCODED_RUSTFLAGS, CARGO_BUILD_RUSTFLAGS),
# and tar/gzip/ripgrep honor TAR_OPTIONS, GZIP, and RIPGREP_CONFIG_PATH, so
# inherited values could build, extract, or gate with unrecorded behavior.
# The sweep runs before any external command, including sort. Swept names are
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

# Bind required commands to fully resolved absolute paths before use. Binding
# the resolved target rather than the PATH name closes the window where a
# mutable symlink is swapped after provenance is written: later gates would
# execute different bytes than the hashed resolved target. realpath resolves
# first because the loop needs it.
required_tools=(
	awk bash cargo cc clippy-driver cmp cp date dirname find findmnt getconf
	git gzip hostname ld ln lsblk lscpu mkdir mktemp mv nm objdump python3
	realpath rg rm rustc rustdoc rustfmt sed sha256sum sort tar touch uname
	xargs cargo-clippy cargo-fmt
)
if ! realpath_path=$(type -P realpath) || [[ $realpath_path != /* ]]; then
	echo "required tool realpath is absent from PATH" >&2
	exit 2
fi
declare -A tool_paths tool_resolved_paths
for tool in "${required_tools[@]}"; do
	if ! tool_path=$(type -P "$tool"); then
		echo "required tool is absent from PATH: $tool" >&2
		exit 2
	fi
	if [[ $tool_path != /* ]]; then
		echo "required tool did not resolve to an absolute path: $tool_path" >&2
		exit 2
	fi
	resolved_tool_path=$("$realpath_path" "$tool_path")
	tool_paths[$tool]=$tool_path
	tool_resolved_paths[$tool]=$resolved_tool_path
	hash -p "$resolved_tool_path" "$tool"
done

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
		# xargs performs its own PATH lookup for a bare command name, so it
		# gets the recorded resolved sha256sum path.
		find . -type f ! -name SHA256SUMS ! -name "$manifest" -print0 |
			LC_ALL=C sort -z |
			xargs -0 "${tool_resolved_paths[sha256sum]}" >"$manifest"
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
# Canonicalize before anything derives from this path: a symlinked TMPDIR
# makes the textual mktemp path and the physical directory children see via
# getcwd diverge, and Cargo, rustfmt, and Clippy probe ancestor configs from
# the physical parents — which the ancestor scan below must therefore walk.
build_root=$("$realpath_path" "$build_root")
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

# cc launches its ld subprogram through its own search, which falls back to
# PATH when the driver's prefix directories hold no ld — so a mutable PATH ld
# shim could link the retained binaries with unrecorded bytes while the
# receipt hashes only cc. A directory holding a single symlink to the hashed
# resolved ld goes first in PATH, so that fallback lookup can only reach the
# recorded bytes. It lives inside the build root (rides its cleanup) and the
# symlink is invisible to the source manifests, which match regular files
# only. A driver-internal ld bypasses PATH; toolchain-dispatch.txt records
# which case applies.
mkdir "$build_root/.topic33-linker-pin-bin"
ln -s "${tool_resolved_paths[ld]}" "$build_root/.topic33-linker-pin-bin/ld"
PATH="$build_root/.topic33-linker-pin-bin:$PATH"
readonly PATH
# Assigning to PATH clears every hashed filename, so the bindings above are
# gone; rebind the recorded resolved targets or later bare-word calls would
# resolve by a fresh PATH search a mutable shim could win.
for tool in "${required_tools[@]}"; do
	hash -p "${tool_resolved_paths[$tool]}" "$tool"
done

mkdir -p "$output/gates"
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Only names for swept variables: this file is sealed into the promoted
# evidence archive and swept values include common secrets. The policy lines
# record the full sweep pattern; the unset lines record which of those
# variables this host actually had set.
{
	echo "refused_startup_names=LD_PRELOAD LD_AUDIT LD_LIBRARY_PATH"
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
	resolved_bash_path=$("$realpath_path" "$BASH")
	printf 'bash_resolved_path=%q\nbash_sha256=%s\n' \
		"$resolved_bash_path" \
		"$(sha256sum "$resolved_bash_path" | awk '{print $1}')"
	# The hashes cover the same stored resolved paths the binding loop gave
	# to hash -p, so the recorded bytes are the bytes the gates execute.
	for tool in "${required_tools[@]}"; do
		resolved_tool_path=${tool_resolved_paths[$tool]}
		tool_sha256=$(sha256sum "$resolved_tool_path" | awk '{print $1}')
		printf '%s_path=%q\n%s_resolved_path=%q\n%s_sha256=%s\n' \
			"$tool" "${tool_paths[$tool]}" "$tool" "$resolved_tool_path" \
			"$tool" "$tool_sha256"
	done
} >"$output/tool-provenance.txt"

# Decompress with the shell-bound gzip and hand tar the plain stream: tar -z
# starts its own gzip through PATH, outside the hash binding, and pipefail
# propagates a gzip failure.
gzip -dc "$verified_archive" | tar -xf - -C "$build_root"
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
# dispatched binaries, check the version against the dispatched compiler,
# export the RUSTC/CARGO/RUSTDOC/RUSTFMT overrides for the tools' own child
# lookups, and hold the dispatched cargo, cargo-fmt, and cargo-clippy paths
# for the gates to invoke directly: a rustup in PATH does not prove the
# PATH-bound cargo words are its proxies, so gates run the recorded
# dispatched bytes, never a command word.
declare -A gate_tool_paths
{
	if rustup_path=$(type -P rustup); then
		# rustup is queried through its resolved path: the PATH name is a
		# mutable symlink that could otherwise be swapped between this hash
		# and the which queries below.
		resolved_rustup_path=$("$realpath_path" "$rustup_path")
		printf 'rustup_path=%q\nrustup_resolved_path=%q\nrustup_sha256=%s\n' \
			"$rustup_path" "$resolved_rustup_path" \
			"$(sha256sum "$resolved_rustup_path" | awk '{print $1}')"
		for component in rustc cargo rustdoc rustfmt cargo-fmt cargo-clippy clippy-driver; do
			dispatched_path=$("$resolved_rustup_path" which "$component")
			resolved_dispatched_path=$("$realpath_path" "$dispatched_path")
			printf '%s_dispatched_path=%q\n%s_dispatched_sha256=%s\n' \
				"$component" "$resolved_dispatched_path" \
				"$component" \
				"$(sha256sum "$resolved_dispatched_path" | awk '{print $1}')"
			case $component in
			rustc)
				dispatched_rustc_path=$resolved_dispatched_path
				export RUSTC="$resolved_dispatched_path"
				;;
			cargo)
				# cargo-fmt and cargo-clippy start `cargo` through the
				# CARGO variable or their own PATH lookup; pin them to the
				# hashed component.
				export CARGO="$resolved_dispatched_path"
				gate_tool_paths[cargo]=$resolved_dispatched_path
				;;
			cargo-fmt)
				gate_tool_paths[cargo-fmt]=$resolved_dispatched_path
				;;
			cargo-clippy)
				gate_tool_paths[cargo-clippy]=$resolved_dispatched_path
				;;
			rustdoc)
				export RUSTDOC="$resolved_dispatched_path"
				;;
			rustfmt)
				export RUSTFMT="$resolved_dispatched_path"
				;;
			esac
		done
		dispatched_rustc_version=$("$dispatched_rustc_path" --version | awk '{print $2}')
		printf 'rustc_dispatched_version=%q\n' "$dispatched_rustc_version"
		if [[ $dispatched_rustc_version != "$pinned_toolchain" ]]; then
			echo "dispatched rustc $dispatched_rustc_version does not match $pinned_toolchain" >&2
			exit 2
		fi
	else
		# rustup installs every proxy as one multiplexer binary, so rustc
		# and cargo resolving to the same file means dispatch flows through
		# a rustup home this run cannot interrogate: no rustup name is in
		# PATH to prove which components would run. A copied multiplexer at
		# distinct paths defeats this test; that residue is covered by the
		# recorded tool and sysroot hashes.
		if [[ ${tool_resolved_paths[rustc]} == "${tool_resolved_paths[cargo]}" ]]; then
			echo "rustc and cargo resolve to one multiplexer binary but rustup is absent from PATH; cannot prove the dispatched toolchain" >&2
			exit 2
		fi
		echo "rustup_path=absent"
		echo "rustc_dispatch=direct"
		export RUSTC="${tool_resolved_paths[rustc]}"
		export CARGO="${tool_resolved_paths[cargo]}"
		export RUSTDOC="${tool_resolved_paths[rustdoc]}"
		export RUSTFMT="${tool_resolved_paths[rustfmt]}"
		gate_tool_paths[cargo]=${tool_resolved_paths[cargo]}
		gate_tool_paths[cargo-fmt]=${tool_resolved_paths[cargo-fmt]}
		gate_tool_paths[cargo-clippy]=${tool_resolved_paths[cargo-clippy]}
	fi
	printf 'gate_cargo=%q\ngate_cargo_fmt=%q\ngate_cargo_clippy=%q\n' \
		"${gate_tool_paths[cargo]}" "${gate_tool_paths[cargo-fmt]}" \
		"${gate_tool_paths[cargo-clippy]}"
	# rustc launches the system linker through its own PATH lookup, which the
	# shell's hash binding does not cover; pin it to the recorded cc for the
	# host target so the retained binaries are linked by the hashed bytes.
	host_target_triple=$("$RUSTC" -vV | sed -n 's/^host: //p')
	if [[ -z $host_target_triple ]]; then
		echo "could not determine the host target triple" >&2
		exit 2
	fi
	linker_variable=CARGO_TARGET_${host_target_triple//-/_}_LINKER
	linker_variable=${linker_variable^^}
	export "$linker_variable"="${tool_resolved_paths[cc]}"
	printf '%s=%q\n' "$linker_variable" "${tool_resolved_paths[cc]}"
	# Which ld the pinned cc will launch: an absolute -print-prog-name answer
	# is a driver-internal linker (record and hash it); a bare name falls back
	# to PATH at link time, where the pinned first entry serves the recorded
	# resolved ld already hashed in tool-provenance.txt.
	cc_reported_ld=$(cc -print-prog-name=ld)
	printf 'cc_reported_ld=%q\n' "$cc_reported_ld"
	if [[ $cc_reported_ld == /* ]]; then
		resolved_cc_ld=$("$realpath_path" "$cc_reported_ld")
		printf 'cc_ld_resolved_path=%q\ncc_ld_sha256=%s\n' "$resolved_cc_ld" \
			"$(sha256sum "$resolved_cc_ld" | awk '{print $1}')"
	else
		printf 'cc_ld_resolution=path_pinned\n'
	fi
	printf 'RUSTC=%q\nCARGO=%q\nRUSTDOC=%q\nRUSTFMT=%q\n' \
		"$RUSTC" "$CARGO" "$RUSTDOC" "$RUSTFMT"
	# The sysroot supplies the standard-library rlibs linked into every
	# retained binary; an unchanged rustc in front of modified lib/rustlib
	# bytes would otherwise leave no trace in the receipt.
	rust_sysroot=$("$RUSTC" --print sysroot)
	printf 'sysroot_path=%q\n' "$rust_sysroot"
	printf 'sysroot_lib_sha256=%s\n' "$(
		cd "$rust_sysroot" &&
			find lib -type f -print0 | LC_ALL=C sort -z |
			xargs -0 "${tool_resolved_paths[sha256sum]}" | sha256sum | awk '{print $1}'
	)"
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
	"$RUSTC" -vV
	"${gate_tool_paths[cargo]}" -V
	cc --version
	objdump --version
	"$RUSTC" --print cfg
	"$RUSTC" -C target-cpu=native --print cfg
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
			xargs -0 "${tool_resolved_paths[sha256sum]}"
	)
}
source_manifest >"$output/source-files.before.sha256"

run_gate() {
	local name=$1
	shift
	(cd "$build_root" && "$@") >"$output/gates/$name.log" 2>&1
}

# Gates invoke the recorded dispatched paths, never a command word: a rustup
# in PATH does not prove the PATH-bound cargo words are its proxies, and
# `cargo fmt`/`cargo clippy` would additionally resolve their external
# subcommands from PATH.
run_gate cargo-fmt "${gate_tool_paths[cargo-fmt]}" --all -- --check
# The top-of-script sweep already cleared RUSTFLAGS and every other Cargo flag
# variable, so the generic build runs with the recorded generic flags.
run_gate cargo-test-package-generic "${gate_tool_paths[cargo]}" test --locked --package topic-033-wal-crash-consistency
run_gate cargo-build-package-generic "${gate_tool_paths[cargo]}" build --locked --release \
	--package topic-033-wal-crash-consistency --bin wal-crash-probe
generic_binary="$build_root/target/release/wal-crash-probe"
cp "$generic_binary" "$output/wal-crash-probe.generic"
sha256sum "$output/wal-crash-probe.generic" >"$output/binary.generic.sha256"
"$generic_binary" model >"$output/model.generic.log" 2>&1
"$generic_binary" process-crash "$output/wal-data/generic-crash" \
	>"$output/process-crash.generic.log" 2>&1

export RUSTFLAGS="-C target-cpu=native"
run_gate cargo-test-package-native "${gate_tool_paths[cargo]}" test --locked --package topic-033-wal-crash-consistency
run_gate cargo-build-package-native "${gate_tool_paths[cargo]}" build --locked --release \
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
run_gate cargo-test-lib-bins-examples "${gate_tool_paths[cargo]}" test --locked --workspace --lib --bins --examples
run_gate cargo-test-doc "${gate_tool_paths[cargo]}" test --locked --workspace --doc
run_gate cargo-clippy "${gate_tool_paths[cargo-clippy]}" --locked --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run "${gate_tool_paths[cargo]}" bench --locked --workspace --no-run
RUSTDOCFLAGS="-D warnings" run_gate cargo-doc "${gate_tool_paths[cargo]}" doc --locked --workspace --no-deps

source_manifest >"$output/source-files.after.sha256"
cmp "$output/source-files.before.sha256" "$output/source-files.after.sha256"
run_completed=1
echo "host run: PASS"
