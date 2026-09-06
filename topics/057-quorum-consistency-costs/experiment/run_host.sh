#!/bin/bash
set -euo pipefail
if [ "$#" -ne 4 ]; then
    echo 'usage: run_host.sh ARCHIVE SHA256 SOURCE_COMMIT EXPECTED_ARCH' >&2
    exit 2
fi
archive=$1
expected_sha=$2
source_commit=$3
expected_arch=$4
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]]
[[ "$expected_sha" =~ ^[0-9a-f]{64}$ ]]
test "$(uname -m)" = "$expected_arch"
test "$(sha256sum "$archive" | cut -d ' ' -f1)" = "$expected_sha"
mkdir source results
archive=$(realpath "$archive")
# git archive records its commit ID in the tar's pax global header.
# source.txt must not publish a commit absent from the digest-verified archive.
archive_commit=$(git get-tar-commit-id < <(gzip -dc "$archive"))
test "$archive_commit" = "$source_commit"
tar -xzf "$archive" -C source
src=source/topics/057-quorum-consistency-costs
cmp "$0" "$src/experiment/run_host.sh"
{
    hostname
    uname -a
    lscpu
    sed -n '1,30p' /proc/cpuinfo
    getconf _NPROCESSORS_ONLN
    nproc
    rustc -Vv
    rustc --print cfg
    printf 'flags: --edition=2024 -C opt-level=2 -D warnings; default target features\n'
} > results/host.txt
printf 'source_commit=%s\narchive_sha256=%s\n' "$source_commit" "$expected_sha" > results/source.txt
sha256sum "$archive" "$0" "$src/src/lib.rs" "$src/examples/quorum.rs" >> results/source.txt
rustc --edition=2024 -C opt-level=2 -D warnings --test "$src/src/lib.rs" -o results/tests
results/tests > results/tests.txt
rustc --edition=2024 -C opt-level=2 -D warnings --crate-name quorum_consistency_costs --crate-type rlib "$src/src/lib.rs" -o results/libquorum_consistency_costs.rlib
rustc --edition=2024 -C opt-level=2 -D warnings --extern quorum_consistency_costs=results/libquorum_consistency_costs.rlib "$src/examples/quorum.rs" -o results/quorum
results/quorum > results/example.txt
rustdoc --edition=2024 -D warnings --test "$src/src/lib.rs" --extern quorum_consistency_costs=results/libquorum_consistency_costs.rlib > results/doctests.txt
rustc --edition=2024 -C opt-level=2 -D warnings --crate-name quorum_consistency_costs --crate-type lib --emit=asm "$src/src/lib.rs" -o results/library.s
objdump -d results/quorum > results/example.disassembly.txt
sha256sum results/tests results/quorum results/libquorum_consistency_costs.rlib results/library.s > results/binaries.sha256
(
    cd results
    sha256sum host.txt source.txt tests.txt example.txt doctests.txt library.s example.disassembly.txt binaries.sha256 > RECEIPT.sha256
)
cat results/tests.txt results/doctests.txt results/example.txt
