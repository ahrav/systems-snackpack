#!/usr/bin/env bash
set -euo pipefail
output="$1"
if [ -e "$output" ]; then
  printf 'output path already exists: %s\n' "$output" >&2
  exit 2
fi
source_commit=$(git rev-parse --verify --quiet "$2^{commit}") || {
  printf 'SOURCE_COMMIT %s is not a commit in this checkout\n' "$2" >&2
  exit 2
}
if [ "$source_commit" != "$(git rev-parse HEAD)" ]; then
  printf 'HEAD %s differs from SOURCE_COMMIT %s\n' "$(git rev-parse HEAD)" "$source_commit" >&2
  exit 2
fi
dirty=$(git status --porcelain --untracked-files=no -- Cargo.lock Cargo.toml rust-toolchain.toml topics/078-bounded-mpmc-queue)
if [ -n "$dirty" ]; then
  printf 'tracked inputs differ from %s:\n%s\n' "$source_commit" "$dirty" >&2
  exit 2
fi
unset CARGO_ENCODED_RUSTFLAGS CARGO_BUILD_RUSTFLAGS CARGO_BUILD_TARGET
for name in $(compgen -v | grep '^CARGO_PROFILE_' || true); do unset "$name"; done
export RUSTFLAGS=""
export CARGO_TARGET_DIR="${CARGO_TARGET_DIR:-target}"
binary="$CARGO_TARGET_DIR/release/bounded-mpmc-queue"
mkdir -p "$output"
{
  printf 'source_commit=%s\n' "$source_commit"
  printf 'RUSTFLAGS=%s\nCARGO_TARGET_DIR=%s\n' "$RUSTFLAGS" "$CARGO_TARGET_DIR"
  hostname
  uname -a
  rustc --version --verbose
  cargo --version
  lscpu
} > "$output/host.txt"
python3 topics/078-bounded-mpmc-queue/model.py > "$output/model.txt"
cargo test --locked -p bounded-mpmc-queue > "$output/tests.txt" 2>&1
python3 -m unittest topics/078-bounded-mpmc-queue/test_run.py >> "$output/tests.txt" 2>&1
cargo clippy --locked -p bounded-mpmc-queue --all-targets -- -D warnings > "$output/clippy.txt" 2>&1
cargo build --locked --release --verbose -p bounded-mpmc-queue > "$output/build.txt" 2>&1
cpus=$(python3 topics/078-bounded-mpmc-queue/select_cpus.py)
printf 'affinity=%s\n' "$cpus" >> "$output/host.txt"
sha256sum "$binary" > "$output/binary.sha256"
taskset -c "$cpus" python3 topics/078-bounded-mpmc-queue/run.py "$binary" "$output/results.json" > "$output/summary.txt"
