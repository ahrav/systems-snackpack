#!/usr/bin/env bash
set -Eeuo pipefail

if [[ -n ${BASH_ENV:-} ]]; then
	echo "exact-source measurement refuses a BASH_ENV startup hook" >&2
	exit 2
fi
if [[ -n $(compgen -A function) ]]; then
	echo "exact-source measurement refuses inherited shell functions" >&2
	exit 2
fi

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
actual_archive_sha256=$(sha256sum "$source_archive" | awk '{print $1}')
if [[ $actual_archive_sha256 != "$expected_archive_sha256" ]]; then
	echo "source archive digest mismatch" >&2
	exit 2
fi
archive_commit=$(gzip -dc "$source_archive" | git get-tar-commit-id)
if [[ $archive_commit != "$source_commit" ]]; then
	echo "Git archive commit $archive_commit does not match $source_commit" >&2
	exit 2
fi

mkdir -p "$output/gates"
trap finalize EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

build_root=$(mktemp -d "${TMPDIR:-/tmp}/topic33-build-root.XXXXXXXX")
touch "$build_root/.topic33-build-root"
tar -xzf "$source_archive" -C "$build_root"
topic="$build_root/topics/033-wal-crash-consistency"
if [[ ! -d $topic ]]; then
	echo "Topic 33 source is absent from archive" >&2
	exit 2
fi
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
	findmnt -T "$output"
	findmnt -T "$output" -n -o SOURCE,FSTYPE,OPTIONS
	lsblk -o NAME,TYPE,SIZE,ROTA,MODEL,FSTYPE,MOUNTPOINTS
} >"$output/host.txt" 2>&1
if findmnt -T "$output" -n -o FSTYPE | rg -q '^tmpfs$'; then
	echo "measurement output and WAL data must not use tmpfs" >&2
	exit 2
fi
{
	echo "generic: RUSTFLAGS unset"
	echo "native: RUSTFLAGS=-C target-cpu=native"
	echo "workspace gates: RUSTFLAGS unset"
	echo "benchmark: 8 blocks, 4 ABBA and 4 BAAB, 32 fresh processes"
	echo "timed region: record writes plus fdatasync only"
} >"$output/build-and-run-flags.txt"

source_manifest() {
	(
		cd "$build_root"
		find . -type f ! -path './target/*' ! -name .topic33-build-root -print0 |
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
unset RUSTFLAGS || true
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
rg -q '[[:space:]][Tt][[:space:]]topic33_crc32c$' "$output/binary.symbols.txt"
objdump -d --no-show-raw-insn --disassemble=topic33_crc32c \
	"$output/wal-crash-probe.native" >"$output/codegen.txt" 2>&1
rg -q '<topic33_crc32c>:' "$output/codegen.txt"
nm -D "$output/wal-crash-probe.native" >"$output/binary.dynamic-symbols.txt" 2>&1 || true
"$native_binary" model >"$output/model.native.log" 2>&1
"$native_binary" process-crash "$output/wal-data/native-crash" \
	>"$output/process-crash.native.log" 2>&1
"$native_binary" bench-run "$output/wal-data/native-bench" \
	"$output/benchmark.csv" 8 128 256 1 8 330033 \
	>"$output/benchmark-run.log" 2>&1
python3 -I "$topic/experiment/validate_receipts.py" \
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
