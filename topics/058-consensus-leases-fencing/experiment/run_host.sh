#!/usr/bin/env bash
set -euo pipefail
umask 077
expected_host=$1
expected_arch=$2
source_commit=$3
archive_hash=$4
runner_hash=$5
[[ "$source_commit" =~ ^[0-9a-f]{40}$ ]]
[[ "$(hostname)" == "$expected_host" ]]
[[ "$(uname -m)" == "$expected_arch" ]]
printf '%s  source.tar\n%s  run_host.sh\n' "$archive_hash" "$runner_hash" | sha256sum -c -
python3 - <<'PY'
from pathlib import Path, PurePosixPath
import tarfile
prefix = 'source/topics/058-consensus-leases-fencing/'
with tarfile.open('source.tar') as archive:
    for member in archive.getmembers():
        name = member.name
        parts = PurePosixPath(name).parts
        assert not name.startswith('/') and '..' not in parts
        assert member.isdir() or member.isfile()
        if member.isdir():
            assert prefix.startswith(name.rstrip('/') + '/') or name.startswith(prefix)
            Path(name).mkdir(parents=True, exist_ok=True)
        else:
            assert name.startswith(prefix)
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(member) as src:
                path.write_bytes(src.read())
PY
topic=source/topics/058-consensus-leases-fencing
cmp run_host.sh "$topic/experiment/run_host.sh"
mkdir receipt
{
  date -u +%FT%TZ
  hostname
  uname -a
  nproc
  lscpu
  rustc -Vv
  rustc --print cfg
  head -n 28 /proc/cpuinfo
  printf '%s\n' 'test flags: --edition 2024 -D warnings -D missing_docs'
  printf '%s\n' 'build flags: --edition 2024 -D warnings -D missing_docs -C opt-level=2; generic target CPU; no LTO'
} > receipt/host.txt
{
  printf 'source_commit=%s\narchive_sha256=%s\nrunner_sha256=%s\n' "$source_commit" "$archive_hash" "$runner_hash"
  sha256sum source.tar run_host.sh "$topic/src/lib.rs" "$topic/examples/handoff.rs"
} > receipt/source.txt
rustc --edition 2024 -D warnings -D missing_docs --test "$topic/src/lib.rs" -o receipt/tests
receipt/tests --test-threads=1 > receipt/tests.txt
rustc --edition 2024 -D warnings -D missing_docs -C opt-level=2 --crate-name consensus_leases_fencing --crate-type rlib --emit link,asm --out-dir receipt "$topic/src/lib.rs"
rustdoc --edition 2024 -D warnings --test --crate-name consensus_leases_fencing "$topic/src/lib.rs" --extern consensus_leases_fencing=receipt/libconsensus_leases_fencing.rlib > receipt/doctests.txt
rustc --edition 2024 -D warnings -D missing_docs -C opt-level=2 "$topic/examples/handoff.rs" --extern consensus_leases_fencing=receipt/libconsensus_leases_fencing.rlib -o receipt/handoff
receipt/handoff > receipt/example.txt
python3 - <<'PY'
from pathlib import Path
text=Path('receipt/consensus_leases_fencing.s').read_text()
lines=text.splitlines()
blocks=[]
for i,line in enumerate(lines):
    if 'accepts_generation' in line and line.endswith(':'):
        end=next((j+1 for j in range(i+1,len(lines)) if lines[j].strip().startswith('.Lfunc_end')),min(i+30,len(lines)))
        blocks.append('\n'.join(lines[i:end]))
assert len(blocks)==1, len(blocks)
Path('receipt/generation-guard.s').write_text(blocks[0]+'\n')
assert '11 passed; 0 failed' in Path('receipt/tests.txt').read_text()
assert '1 passed; 0 failed' in Path('receipt/doctests.txt').read_text()
assert Path('receipt/example.txt').read_text()=='stale_accepted=false final_value=20\nunion_majority=true joint_majority=false\n'
PY
(cd receipt && sha256sum host.txt source.txt tests tests.txt libconsensus_leases_fencing.rlib consensus_leases_fencing.s doctests.txt handoff example.txt generation-guard.s > SHA256SUMS)
chmod a-w receipt/*
cat receipt/example.txt
printf 'FINAL_OK source_commit=%s arch=%s\n' "$source_commit" "$expected_arch"
