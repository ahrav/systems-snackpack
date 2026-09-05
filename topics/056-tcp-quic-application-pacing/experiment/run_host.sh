#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
umask 077
[[ $# == 4 ]] || { echo 'usage: run_host.sh arch archive-sha runner-sha source-head' >&2; exit 2; }
expected_arch=$1
archive_sha=$2
runner_sha=$3
source_head=$4
[[ $expected_arch == aarch64 || $expected_arch == x86_64 ]]
[[ $archive_sha =~ ^[0-9a-f]{64}$ && $runner_sha =~ ^[0-9a-f]{64}$ && $source_head =~ ^[0-9a-f]{40}$ ]]
[[ $(uname -m) == "$expected_arch" ]]
[[ $(sha256sum source.tar.gz | cut -d ' ' -f 1) == "$archive_sha" ]]
[[ $(sha256sum "$0" | cut -d ' ' -f 1) == "$runner_sha" ]]
[[ ! -e receipt && ! -e source ]]
mkdir receipt source
topic=topics/056-tcp-quic-application-pacing
python3 - "$topic" <<'PY'
import sys, tarfile
from pathlib import PurePosixPath
prefix = sys.argv[1] + "/"
with tarfile.open("source.tar.gz") as archive:
    for item in archive.getmembers():
        p = PurePosixPath(item.name)
        assert not p.is_absolute() and ".." not in p.parts
        assert item.isdir() or item.isfile()
        assert item.name.startswith(prefix) or (item.isdir() and item.name in ("topics", prefix[:-1]))
    archive.extractall("source", filter="data")
PY
cmp "$0" "source/$topic/experiment/run_host.sh"
{
    date -u +%Y-%m-%dT%H:%M:%SZ
    hostname
    uname -a
    uname -m
    getconf _NPROCESSORS_ONLN
    nproc
    lscpu
    cat /proc/cpuinfo
    rustc -Vv
    rustc --print cfg
} > receipt/host.txt
printf 'source_head=%s\narchive_sha256=%s\nrunner_sha256=%s\nexpected_arch=%s\nflags=--edition=2024 -D warnings -C opt-level=2; default target CPU/features\n' \
    "$source_head" "$archive_sha" "$runner_sha" "$expected_arch" > receipt/identity.txt
(cd source && find "$topic" -type f -print0 | sort -z | xargs -0 sha256sum) > receipt/source-before.sha256
rustc --edition=2024 -D warnings -C opt-level=2 --test "source/$topic/src/lib.rs" -o receipt/library-tests
./receipt/library-tests > receipt/tests.txt
rustc --edition=2024 -D warnings -C opt-level=2 "source/$topic/examples/pacing.rs" -o receipt/pacing
./receipt/pacing > receipt/example.txt
rustc --edition=2024 -D warnings -C opt-level=2 --emit=asm "source/$topic/examples/pacing.rs" -o receipt/pacing.s
rustc --edition=2024 -D warnings -C opt-level=2 --test --emit=asm "source/$topic/src/lib.rs" -o receipt/library-tests.s
objdump -d receipt/pacing > receipt/pacing.objdump
(cd source && find "$topic" -type f -print0 | sort -z | xargs -0 sha256sum) > receipt/source-after.sha256
cmp receipt/source-before.sha256 receipt/source-after.sha256
python3 - <<'PY'
from pathlib import Path
expected = (
    "pause=false overdue_burst=1 capped_burst=2 overdue_finish_us=9900 capped_finish_us=9800\n"
    "pause=true overdue_burst=51 capped_burst=2 overdue_finish_us=9900 capped_finish_us=14700\n"
)
assert Path("receipt/example.txt").read_text() == expected
assert "7 passed; 0 failed" in Path("receipt/tests.txt").read_text()
PY
(cd receipt && find . -type f ! -name MANIFEST.sha256 -print0 | sort -z | xargs -0 sha256sum) > receipt/MANIFEST.sha256
chmod -R a-w receipt
tar -czf receipt.tar.gz receipt
sha256sum receipt.tar.gz
cat receipt/tests.txt receipt/example.txt
