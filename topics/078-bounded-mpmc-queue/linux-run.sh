#!/usr/bin/env bash
set -euo pipefail
output="$1"
source_commit="$2"
mkdir -p "$output"
{
  printf 'source_commit=%s\n' "$source_commit"
  hostname
  uname -a
  rustc --version --verbose
  cargo --version
  lscpu
} > "$output/host.txt"
python3 topics/078-bounded-mpmc-queue/model.py > "$output/model.txt"
cargo test --locked -p bounded-mpmc-queue > "$output/tests.txt" 2>&1
cargo clippy --locked -p bounded-mpmc-queue --all-targets -- -D warnings > "$output/clippy.txt" 2>&1
cargo build --locked --release -p bounded-mpmc-queue > "$output/build.txt" 2>&1
cpus=$(python3 - <<'PY'
import os, subprocess
allowed = os.sched_getaffinity(0)
rows = subprocess.check_output(['lscpu', '-p=CPU,CORE,SOCKET'], text=True)
selected, seen, socket = [], set(), None
for line in rows.splitlines():
    if line.startswith('#'):
        continue
    cpu, core, sock = map(int, line.split(','))
    if cpu not in allowed or (sock, core) in seen:
        continue
    if socket is None:
        socket = sock
    if sock != socket:
        continue
    seen.add((sock, core))
    selected.append(cpu)
    if len(selected) == 8:
        break
assert len(selected) == 8, 'campaign requires eight available physical cores on one socket'
print(','.join(map(str, selected)))
PY
)
printf 'affinity=%s\n' "$cpus" >> "$output/host.txt"
sha256sum target/release/bounded-mpmc-queue > "$output/binary.sha256"
taskset -c "$cpus" python3 topics/078-bounded-mpmc-queue/run.py target/release/bounded-mpmc-queue "$output/results.json" > "$output/summary.txt"
