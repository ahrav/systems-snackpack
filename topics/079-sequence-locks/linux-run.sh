#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.cargo/bin:$PATH"
cd "$(dirname "$0")"
mkdir -p measurements/run
{
  date -u +%FT%TZ
  hostname
  uname -a
  lscpu
  rustc -Vv
  cargo -V
  python3 --version
  printf 'allowed CPUs: '
  taskset -pc $$
  lscpu -p=CPU,CORE,SOCKET
} > measurements/run/host.txt
python3 model.py > measurements/run/model.txt
cargo test --locked -p sequence-locks > measurements/run/tests.txt 2>&1
cargo clippy --locked -p sequence-locks --all-targets -- -D warnings > measurements/run/clippy.txt 2>&1
cargo build --locked --release -p sequence-locks > measurements/run/build.txt 2>&1
cpus=$(python3 select_cpus.py)
printf '\nselected CPU set: %s\n' "$cpus" >> measurements/run/host.txt
sha256sum ../../target/release/sequence-locks > measurements/run/binary.sha256
python3 run.py --binary ../../target/release/sequence-locks --cpus "$cpus" --out measurements/run/results.json > measurements/run/summary.txt
