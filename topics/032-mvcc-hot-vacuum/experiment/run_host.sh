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

loader_environment_names=()
while IFS= read -r variable; do
	case $variable in
	LD_* | DYLD_* | GLIBC_TUNABLES)
		loader_environment_names+=("$variable")
		unset "$variable"
		;;
	esac
done < <(compgen -e)
if [[ -s /etc/ld.so.preload ]]; then
	echo "exact-source measurement refuses /etc/ld.so.preload interposition" >&2
	exit 2
fi

required_tools=(
	awk cargo cc comm cmp cp date dirname env find getconf git gzip hostname
	lscpu mkdir mktemp mv nm objdump python3 realpath rg rm rustc sed sha256sum
	sort tar touch tr uname xargs
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
		if ! find . -type f ! -name SHA256SUMS ! -name "$manifest" -print0 |
			LC_ALL=C sort -z |
			xargs -0 sha256sum >"$manifest"; then
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
	# Scratch trees are removed before sealing so a scratch path under
	# $output can never leave SHA256SUMS naming deleted files.
	if [[ -n $cargo_home && -f $cargo_home/.topic32-cargo-home ]]; then
		rm -rf "$cargo_home"
	fi
	if [[ -n $build_root && -f $build_root/.topic32-build-root ]]; then
		rm -rf "$build_root"
	fi
	if [[ -d $output ]]; then
		if ((exit_code == 0 && run_completed == 1)); then
			write_run_status success 0
		else
			if ((exit_code == 0)); then
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
	exit "$exit_code"
}

if [[ $(uname -s) != Linux ]]; then
	echo "run_host.sh requires Linux" >&2
	exit 2
fi

if [[ ! -d "$repository/topics/032-mvcc-hot-vacuum" ]]; then
	echo "Topic 32 source is absent from repository: $repository" >&2
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

# Swept values are never written: this file is sealed into the promoted
# evidence archive, and swept variables include common secrets (PGPASSWORD,
# CARGO_ registry tokens). Only names are recorded for unset variables.
{
	echo "swept_prefixes=CARGO_ GIT_ RUST LD_ DYLD_ PG"
	for variable_name in "${loader_environment_names[@]}"; do
		printf 'unset %s\n' "$variable_name"
	done
	while IFS= read -r variable; do
		case $variable in
		RUSTUP_HOME | GIT_NO_REPLACE_OBJECTS)
			printf 'kept %s=%q\n' "$variable" "${!variable}"
			;;
		AR | ARFLAGS | AS | CC | CFLAGS | CPP | CPPFLAGS | CXX | CXXFLAGS | \
			LD | LDFLAGS | LIBRARY_PATH | CPATH | C_INCLUDE_PATH | \
			CPLUS_INCLUDE_PATH | MAKEFLAGS | NM | OBJCOPY | OBJDUMP | \
			PKG_CONFIG | PKG_CONFIG_PATH | RANLIB | RIPGREP_CONFIG_PATH | \
			STRIP | TAR_OPTIONS | PYTHON* | VIRTUAL_ENV | CARGO_* | \
			GIT_* | RUST* | PG*)
			printf 'unset %s\n' "$variable"
			unset "$variable"
			;;
		esac
	done < <(compgen -e | LC_ALL=C sort)
} >"$output/environment.before.txt"

{
	printf 'bash_path=%q\nbash_version=%q\nPATH=%q\n' \
		"$BASH" "$BASH_VERSION" "$PATH"
	resolved_bash_path=$(realpath "$BASH")
	printf 'bash_resolved_path=%q\nbash_sha256=%s\n' \
		"$resolved_bash_path" "$(sha256sum "$resolved_bash_path" | awk '{ print $1 }')"
	for tool in "${required_tools[@]}"; do
		tool_path=${tool_paths[$tool]}
		resolved_tool_path=$(realpath "$tool_path")
		tool_sha256=$(sha256sum "$resolved_tool_path" | awk '{ print $1 }')
		printf '%s_path=%q\n%s_resolved_path=%q\n%s_sha256=%s\n' \
			"$tool" "$tool_path" "$tool" "$resolved_tool_path" \
			"$tool" "$tool_sha256"
	done
} >"$output/tool-provenance.txt"

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
if rg -q '^(S|[a-z]) ' <<<"$marked_files"; then
	echo "exact-source measurement refuses assume-unchanged or skip-worktree files" >&2
	exit 2
fi
if ! git -C "$repository" ls-files -z |
	git -C "$repository" check-attr --stdin -z \
		filter ident export-ignore export-subst |
	tr '\0' '\n' |
	awk 'NR % 3 == 0 && $0 != "unspecified" && $0 != "unset" { bad = 1 } END { exit bad }'; then
	echo "exact-source measurement refuses content-transforming Git attributes" >&2
	exit 2
fi

git -C "$repository" archive --format=tar "$source_commit" |
	gzip -n -9 >"$output/source.tar.gz"
source_archive_sha256=$(sha256sum "$output/source.tar.gz" | awk '{print $1}')

build_root=$(mktemp -d "${TMPDIR:-/tmp}/topic32-build-root.XXXXXXXX")
touch "$build_root/.topic32-build-root"
tar -xzf "$output/source.tar.gz" -C "$build_root"
topic="$build_root/topics/032-mvcc-hot-vacuum"

pinned_toolchain=$(sed -n 's/^channel = "\(.*\)"$/\1/p' \
	"$build_root/rust-toolchain.toml")
resolved_rustc=$(cd "$build_root" && rustc --version | awk '{print $2}')
if [[ -z $pinned_toolchain || $resolved_rustc != "$pinned_toolchain" ]]; then
	printf 'resolved rustc %s does not match the pinned toolchain %s\n' \
		"$resolved_rustc" "${pinned_toolchain:-unparsed}" >&2
	exit 2
fi

cargo_home=$(mktemp -d "${TMPDIR:-/tmp}/topic32-cargo-home.XXXXXXXX")
touch "$cargo_home/.topic32-cargo-home"
export CARGO_HOME="$cargo_home"
export CARGO_NET_OFFLINE=true
{
	printf 'CARGO_HOME=%q\n' "$CARGO_HOME"
	printf 'CARGO_NET_OFFLINE=%q\n' "$CARGO_NET_OFFLINE"
} >"$output/environment.effective.txt"

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
			-g '!**/__pycache__/**' -g '!**/.ruff_cache/**' |
			LC_ALL=C sort -z
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
			! -name .topic32-build-root \
			-print0 |
			LC_ALL=C sort -z |
			xargs -0 sha256sum
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
	--package mvcc-hot-vacuum
run_gate cargo-build-package-generic cargo build --locked --release \
	--package mvcc-hot-vacuum --bin mvcc-hot-vacuum-probe

generic_binary="$build_root/target/release/mvcc-hot-vacuum-probe"
cp "$generic_binary" "$output/mvcc-hot-vacuum-probe.generic"
sha256sum "$output/mvcc-hot-vacuum-probe.generic" >"$output/binary.generic.sha256"
python3 -I "$topic/experiment/run_processes.py" \
	"$generic_binary" \
	"$output/experiment-generic" >"$output/process-runner.generic.log" 2>&1
python3 -I "$topic/experiment/validate_receipts.py" \
	"$output/experiment-generic" "$output/mvcc-hot-vacuum-probe.generic" \
	>"$output/validation.generic.log" 2>&1
generic_recorded_sha256=$(awk 'NR == 1 { print $1 }' \
	"$output/experiment-generic/binary.sha256")
generic_actual_sha256=$(sha256sum "$output/mvcc-hot-vacuum-probe.generic" |
	awk '{ print $1 }')
[[ $generic_recorded_sha256 == "$generic_actual_sha256" ]]

export RUSTFLAGS="-C target-cpu=native"
run_gate cargo-test-package-native cargo test --locked \
	--package mvcc-hot-vacuum
run_gate cargo-build-package-native cargo build --locked --release \
	--package mvcc-hot-vacuum --bin mvcc-hot-vacuum-probe

binary="$build_root/target/release/mvcc-hot-vacuum-probe"
cp "$binary" "$output/mvcc-hot-vacuum-probe.native"
sha256sum "$output/mvcc-hot-vacuum-probe.native" >"$output/binary.native.sha256"
nm -n "$output/mvcc-hot-vacuum-probe.native" >"$output/binary.symbols.txt"
symbols=(
	topic32_xid_visible_bounds
	topic32_reclaimable_before
)
for symbol in "${symbols[@]}"; do
	rg -q "[[:space:]][Tt][[:space:]]${symbol}$" \
		"$output/binary.symbols.txt"
	objdump -d --no-show-raw-insn --disassemble="$symbol" \
		"$output/mvcc-hot-vacuum-probe.native"
done >"$output/codegen.txt" 2>&1
for symbol in "${symbols[@]}"; do
	rg -q "<${symbol}>:" "$output/codegen.txt"
done

python3 -I "$topic/experiment/run_processes.py" "$binary" \
	"$output/experiment-native" >"$output/process-runner.native.log" 2>&1
python3 -I "$topic/experiment/validate_receipts.py" \
	"$output/experiment-native" "$output/mvcc-hot-vacuum-probe.native" \
	>"$output/validation.native.log" 2>&1
native_recorded_sha256=$(awk 'NR == 1 { print $1 }' \
	"$output/experiment-native/binary.sha256")
native_actual_sha256=$(sha256sum "$output/mvcc-hot-vacuum-probe.native" |
	awk '{ print $1 }')
[[ $native_recorded_sha256 == "$native_actual_sha256" ]]

unset RUSTFLAGS
run_gate cargo-test-lib-examples cargo test --locked --workspace --lib --bins --examples
run_gate cargo-test-doc cargo test --locked --workspace --doc
run_gate cargo-clippy cargo clippy --locked --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --locked --workspace --no-run
run_gate cargo-doc env "RUSTDOCFLAGS=-D warnings" cargo doc --locked --workspace --no-deps

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
