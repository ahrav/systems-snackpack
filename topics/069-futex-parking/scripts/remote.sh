#!/bin/bash
set -euo pipefail
mkdir -p evidence
sha256sum -c INPUTS.sha256 > evidence/input-check.txt
{
  hostname
  uname -a
  lscpu
  rustc -Vv
  nproc
  taskset -pc $$
  rustc -C target-cpu=native --print cfg
} > evidence/host.txt
rustc --edition=2024 -D warnings --test src/lib.rs -o tests
timeout 60 ./tests > evidence/tests.txt 2>&1
rustc --edition=2024 -D warnings -C opt-level=3 -C target-cpu=native --crate-name futex_parking --crate-type rlib src/lib.rs -o libfutex_parking.rlib
rustc --edition=2024 -D warnings -C opt-level=3 -C target-cpu=native examples/compare.rs --extern futex_parking=libfutex_parking.rlib -o compare
rustdoc --edition=2024 --test src/lib.rs --extern futex_parking=libfutex_parking.rlib > evidence/doctest.txt 2>&1
objdump -d ./compare > evidence/assembly.txt
sha256sum compare libfutex_parking.rlib > evidence/binaries.sha256
python3 scripts/run.py "$PWD/compare" evidence
sha256sum -c INPUTS.sha256 > evidence/final-input-check.txt
