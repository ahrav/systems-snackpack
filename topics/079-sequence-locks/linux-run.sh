#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.cargo/bin:$PATH"
output=$(realpath -m -- "${1:-$(dirname "$0")/measurements/run}")
cd "$(dirname "$0")"
if [ -e "$output" ]; then
  printf 'output path already exists: %s\n' "$output" >&2
  exit 2
fi
source_commit=$(git rev-parse --verify HEAD)
dirty=$(git status --porcelain --untracked-files=all -- ../../Cargo.lock ../../Cargo.toml ../../rust-toolchain.toml .)
if [ -n "$dirty" ]; then
  printf 'build inputs differ from %s:\n%s\n' "$source_commit" "$dirty" >&2
  exit 2
fi
mkdir -p "$output"
{
  printf 'source_commit=%s\n' "$source_commit"
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
} > "$output"/host.txt
python3 model.py > "$output"/model.txt
cargo test --locked -p sequence-locks > "$output"/tests.txt 2>&1
cargo clippy --locked -p sequence-locks --all-targets -- -D warnings > "$output"/clippy.txt 2>&1
cargo build --locked --release -p sequence-locks > "$output"/build.txt 2>&1
cpus=$(python3 select_cpus.py)
printf '\nselected CPU set: %s\n' "$cpus" >> "$output"/host.txt
sha256sum ../../target/release/sequence-locks > "$output"/binary.sha256
python3 run.py --binary ../../target/release/sequence-locks --cpus "$cpus" --out "$output"/results.json > "$output"/summary.txt
