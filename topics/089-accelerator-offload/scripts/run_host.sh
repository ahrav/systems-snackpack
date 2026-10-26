#!/usr/bin/env bash
set -euo pipefail
: "${SOURCE_COMMIT:?set the source commit}"
: "${RESULT_DIR:?set the output directory}"
mkdir -p "$RESULT_DIR"
{
  uname -a
  command -v cargo
  rustc -Vv
  for tool in nvcc nvidia-smi; do
    if command -v "$tool"; then "$tool" --version; else printf '%s unavailable\n' "$tool"; fi
  done
  for node in /dev/nvidia0 /dev/nvidiactl /dev/dri; do
    if test -e "$node"; then ls -ld "$node"; else printf '%s unavailable\n' "$node"; fi
  done
} > "$RESULT_DIR/environment.txt" 2>&1
cargo test -p accelerator-offload > "$RESULT_DIR/tests.log" 2>&1
cargo build --release -p accelerator-offload > "$RESULT_DIR/build.log" 2>&1
python3 topics/089-accelerator-offload/scripts/oracle.py target/release/accelerator-offload > "$RESULT_DIR/oracle.json"
python3 topics/089-accelerator-offload/scripts/measure.py target/release/accelerator-offload "$RESULT_DIR" > "$RESULT_DIR/campaign.log"
