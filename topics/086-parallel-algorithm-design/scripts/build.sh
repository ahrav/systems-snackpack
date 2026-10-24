#!/usr/bin/env bash
set -euo pipefail
# Runs from the topic directory regardless of the caller's working directory. The toolchain must already be installed.
cd "$(dirname "${BASH_SOURCE[0]}")/.."
mkdir -p build
RUSTC=(rustup run 1.93.1 rustc)
FLAGS=(--edition=2024 -C opt-level=3 -C target-cpu=native -C codegen-units=1 -C lto=off -C panic=unwind)
"${RUSTC[@]}" -Vv > build/toolchain.txt
"${RUSTC[@]}" "${FLAGS[@]}" --test src/lib.rs -o build/tests
./build/tests
"${RUSTC[@]}" "${FLAGS[@]}" --crate-name parallel_algorithm_design --crate-type rlib src/lib.rs -o build/libparallel_algorithm_design.rlib
"${RUSTC[@]}" "${FLAGS[@]}" src/main.rs --extern parallel_algorithm_design=build/libparallel_algorithm_design.rlib -o build/probe
python3 scripts/oracle.py ./build/probe
