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

# LD_PRELOAD, LD_AUDIT, and GLIBC_TUNABLES change allocator and libc behavior in
# Cargo, rustc, and every probe process, which would silently move the timings
# the run promotes as evidence.
loader_environment_names=()
loader_environment_values=()
while IFS= read -r variable; do
	case $variable in
	LD_* | DYLD_* | GLIBC_TUNABLES | MALLOC_*)
		loader_environment_names+=("$variable")
		loader_environment_values+=("${!variable}")
		unset "$variable"
		;;
	esac
done < <(compgen -e)
if [[ -s /etc/ld.so.preload ]]; then
	echo "exact-source measurement refuses /etc/ld.so.preload interposition" >&2
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
run_started_utc=$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)
source_archive_sha256=not-recorded
cargo_home=
build_root=
run_completed=0

if [[ $(uname -s) != Linux ]]; then
	echo "run_host.sh requires Linux" >&2
	exit 2
fi
if [[ ! $source_commit =~ ^[0-9a-f]{40}$ ]]; then
	echo "source commit must be 40 lowercase hexadecimal characters" >&2
	exit 2
fi
if [[ -z $host_label || $host_label == *$'\n'* || $host_label == *$'\r'* ]]; then
	echo "host label must be non-empty and single-line" >&2
	exit 2
fi
machine_architecture=$(uname -m)
case $host_label in
arm | arm-required) expected_architecture=aarch64 ;;
xxl | xxl-resolved) expected_architecture=x86_64 ;;
*)
	echo "host label must be arm, arm-required, xxl, or xxl-resolved" >&2
	exit 2
	;;
esac
if [[ $machine_architecture != "$expected_architecture" ]]; then
	printf 'host label %s requires architecture %s, found %s\n' \
		"$host_label" "$expected_architecture" "$machine_architecture" >&2
	exit 2
fi
if [[ ! -d $repository/topics/031-database-index-internals ]]; then
	echo "Topic 31 source is absent from repository: $repository" >&2
	exit 2
fi
if [[ -e $output ]]; then
	echo "output already exists: $output" >&2
	exit 2
fi
case "$output/" in
"$repository/"*)
	echo "output must be outside the source tree" >&2
	exit 2
	;;
esac

required_tools=(
	awk bash cargo cc cmp cp date env git gzip hostname lscpu mkdir mktemp mv nm
	objdump python3 realpath rg rm rustc sed sha256sum sort tar taskset touch tr uname xargs
)
for tool in "${required_tools[@]}"; do
	if ! type -P "$tool" >/dev/null; then
		echo "required tool is absent from PATH: $tool" >&2
		exit 2
	fi
done

seal_evidence() {
	(
		cd "$output"
		rg --files -0 --hidden --no-ignore \
			-g '!SHA256SUMS' -g '!SHA256SUMS.tmp' |
			LC_ALL=C sort -z |
			xargs -0 sha256sum >SHA256SUMS.tmp
		mv SHA256SUMS.tmp SHA256SUMS
		sha256sum --check --quiet SHA256SUMS
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

finish() {
	local exit_code=$?
	trap - EXIT
	set +e
	if [[ -n $cargo_home && -f $cargo_home/.topic31-cargo-home ]]; then
		rm -rf "$cargo_home"
	fi
	if [[ -n $build_root && -f $build_root/.topic31-build-root ]]; then
		rm -rf "$build_root"
	fi
	if [[ -d $output ]]; then
		if ((exit_code == 0 && run_completed == 1)); then
			write_run_status success 0
		else
			((exit_code == 0)) && exit_code=1
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

mkdir -p "$output/gates"
trap finish EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
trap 'exit 129' HUP

{
	echo "swept_prefixes=CARGO_ GIT_ RUST LD_ DYLD_ MALLOC_"
	for variable_index in "${!loader_environment_names[@]}"; do
		printf 'unset %s=%q\n' \
			"${loader_environment_names[$variable_index]}" \
			"${loader_environment_values[$variable_index]}"
	done
	while IFS= read -r variable; do
		case $variable in
		RUSTUP_HOME | GIT_NO_REPLACE_OBJECTS)
			printf 'kept %s=%q\n' "$variable" "${!variable}"
			;;
		CARGO_* | GIT_* | RUST*)
			echo "unset $variable"
			unset "$variable"
			;;
		esac
	done < <(compgen -e | LC_ALL=C sort)
} >"$output/environment.before.txt"

repository_root=$(git -C "$repository" rev-parse --show-toplevel)
if [[ $(realpath "$repository_root") != "$repository" ]]; then
	echo "repository must be the root of its Git worktree" >&2
	exit 2
fi
if [[ $(git -C "$repository" rev-parse HEAD) != "$source_commit" ]]; then
	echo "HEAD does not equal requested source commit" >&2
	exit 2
fi
if [[ -n $(git -C "$repository" status --porcelain=v1 --untracked-files=all) ]]; then
	echo "exact-source measurement requires a clean worktree" >&2
	exit 2
fi
if git -C "$repository" ls-files -v | rg -q '^(S|[a-z]) '; then
	echo "exact-source measurement refuses skip-worktree or assume-unchanged files" >&2
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

git -C "$repository" ls-files -z >"$output/tracked-files.z"
git -C "$repository" archive --format=tar "$source_commit" |
	gzip -n -9 >"$output/source.tar.gz"
source_archive_sha256=$(sha256sum "$output/source.tar.gz" | awk '{print $1}')

build_root=$(mktemp -d "${TMPDIR:-/tmp}/topic31-build-root.XXXXXXXX")
touch "$build_root/.topic31-build-root"
cargo_home=$(mktemp -d "${TMPDIR:-/tmp}/topic31-cargo-home.XXXXXXXX")
touch "$cargo_home/.topic31-cargo-home"
export CARGO_HOME="$cargo_home"
printf 'CARGO_HOME=%q\n' "$CARGO_HOME" >"$output/environment.effective.txt"
tar -xzf "$output/source.tar.gz" -C "$build_root"
topic="$build_root/topics/031-database-index-internals"

pinned_toolchain=$(sed -n 's/^channel = "\(.*\)"$/\1/p' \
	"$build_root/rust-toolchain.toml")
resolved_rustc=$(cd "$build_root" && rustc --version | awk '{print $2}')
if [[ -z $pinned_toolchain || $resolved_rustc != "$pinned_toolchain" ]]; then
	printf 'resolved rustc %s does not match pinned toolchain %s\n' \
		"$resolved_rustc" "${pinned_toolchain:-unparsed}" >&2
	exit 2
fi

{
	printf 'host_label=%q\n' "$host_label"
	echo "expected_architecture=$expected_architecture"
	echo "machine_architecture=$machine_architecture"
	echo "source_commit=$source_commit"
	echo "source_archive_sha256=$source_archive_sha256"
} >"$output/source_identity.txt"

(
	cd "$build_root"
	printf 'host_label=%q\n' "$host_label"
	hostname -f
	uname -a
	uname -m
	lscpu
	rustc -vV
	cargo -V
	cc --version
	objdump --version
	rustc --print cfg
	rustc -C target-cpu=native --print cfg
	cc -march=native -Q --help=target
) >"$output/host.txt" 2>&1

{
	echo "generic: CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1; RUSTFLAGS unset"
	echo "native: CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1; RUSTFLAGS=-C target-cpu=native"
	echo "runner: 12 blocks; alternating ABBA/BAAB; taskset -c 0"
	echo "dataset: TOPIC31_ENTRIES=1048576 TOPIC31_QUERIES=65536 TOPIC31_REPS=8"
} >"$output/build-flags.txt"

source_manifest() {
	(
		cd "$build_root"
		xargs -0 sha256sum <"$output/tracked-files.z"
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

export CARGO_NET_OFFLINE=true
export CARGO_PROFILE_RELEASE_CODEGEN_UNITS=1
run_gate cargo-fmt cargo fmt --all -- --check
run_gate cargo-test-package-generic cargo test --locked \
	--package database-index-internals
run_gate cargo-build-package-generic env \
	CARGO_TARGET_DIR="$build_root/target-generic" \
	cargo build --locked --release --package database-index-internals \
	--bin index-layout-probe

generic_binary="$build_root/target-generic/release/index-layout-probe"
cp "$generic_binary" "$output/index-layout-probe.generic"
sha256sum "$output/index-layout-probe.generic" >"$output/binary.generic.sha256"
python3 -I "$topic/experiment/run_processes.py" \
	"$output/index-layout-probe.generic" "$output/experiment-generic" \
	>"$output/process-runner.generic.log" 2>&1
python3 -I "$topic/experiment/summarize.py" \
	"$output/experiment-generic" >"$output/summary.generic.log" 2>&1

export RUSTFLAGS="-C target-cpu=native"
run_gate cargo-test-package-native env \
	CARGO_TARGET_DIR="$build_root/target-native" \
	cargo test --locked --package database-index-internals
run_gate cargo-build-package-native env \
	CARGO_TARGET_DIR="$build_root/target-native" \
	cargo build --locked --release --package database-index-internals \
	--bin index-layout-probe

native_binary="$build_root/target-native/release/index-layout-probe"
cp "$native_binary" "$output/index-layout-probe.native"
sha256sum "$output/index-layout-probe.native" >"$output/binary.native.sha256"
nm -n "$output/index-layout-probe.native" >"$output/binary.symbols.txt"
symbols=(topic31_narrow_lookup topic31_covering_lookup)
for symbol in "${symbols[@]}"; do
	rg -q "[[:space:]][Tt][[:space:]]${symbol}$" "$output/binary.symbols.txt"
	objdump -d --no-show-raw-insn --disassemble="$symbol" \
		"$output/index-layout-probe.native"
done >"$output/codegen.txt" 2>&1
for symbol in "${symbols[@]}"; do
	rg -q "<${symbol}>:" "$output/codegen.txt"
done

python3 -I "$topic/experiment/run_processes.py" \
	"$output/index-layout-probe.native" "$output/experiment-native" \
	>"$output/process-runner.native.log" 2>&1
python3 -I "$topic/experiment/summarize.py" \
	"$output/experiment-native" >"$output/summary.native.log" 2>&1

unset RUSTFLAGS
unset CARGO_TARGET_DIR || true
run_gate cargo-test-lib-examples cargo test --workspace --lib --examples
run_gate cargo-test-doc cargo test --workspace --doc
run_gate cargo-clippy cargo clippy --workspace --all-targets -- -D warnings
run_gate cargo-bench-no-run cargo bench --workspace --no-run
run_gate cargo-doc env "RUSTDOCFLAGS=-D warnings" cargo doc --workspace --no-deps

source_manifest >"$output/source-files.after.sha256"
cmp "$output/source-files.before.sha256" "$output/source-files.after.sha256"
if [[ $(git -C "$repository" rev-parse HEAD) != "$source_commit" ]]; then
	echo "HEAD changed during measurement" >&2
	exit 1
fi
if [[ -n $(git -C "$repository" status --porcelain=v1 --untracked-files=all) ]]; then
	echo "source worktree changed during measurement" >&2
	exit 1
fi

run_completed=1
echo "host run: PASS"
