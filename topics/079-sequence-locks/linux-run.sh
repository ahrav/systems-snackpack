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
unset CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET
for name in $(compgen -v | grep '^CARGO_PROFILE_' || true); do unset "$name"; done
export RUSTFLAGS=""
CARGO_TARGET_DIR=$(realpath -m -- "${CARGO_TARGET_DIR:-../../target}")
export CARGO_TARGET_DIR
target=$(rustc -vV | sed -n 's/^host: //p')
binary="$CARGO_TARGET_DIR/$target/release/sequence-locks"
mkdir -p "$output"
{
  printf 'source_commit=%s\n' "$source_commit"
  printf 'RUSTFLAGS=%s\nCARGO_TARGET_DIR=%s\n' "$RUSTFLAGS" "$CARGO_TARGET_DIR"
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
python3 -m unittest test_run.py >> "$output"/tests.txt 2>&1
cargo clippy --locked -p sequence-locks --all-targets -- -D warnings > "$output"/clippy.txt 2>&1
cargo build --locked --release --verbose --target "$target" -p sequence-locks > "$output"/build.txt 2>&1
cpus=$(python3 select_cpus.py)
printf '\nselected CPU set: %s\n' "$cpus" >> "$output"/host.txt
sha256sum "$binary" > "$output"/binary.sha256
python3 run.py --binary "$binary" --cpus "$cpus" --out "$output"/results.json > "$output"/summary.txt
