# Measurement contract

This topic retains correctness and generated-code evidence, not a timing
comparison.

## Required records

Each promoted host record names:

- source commit and shared source-archive SHA-256;
- SSH target, resolved hostname, architecture, kernel, CPU identity, and
  available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, native target features, and
  build flags;
- eight generic-build and eight native-build fresh-process receipts, with an
  independent validation result for each set;
- final binary hash, exported symbols, and disassembly;
- workspace-gate outcomes; and
- a before/after source manifest proving the run did not rewrite source.

## Interpretation

Matching deterministic outputs on two hosts establish portability for the two
retained source, compiler, binary, host, and run-window combinations. They do
not compare processor architectures or establish live clock accuracy.

Raw logs are retained as one compressed archive per host. The outer
`SHA256SUMS` file verifies those archives after retrieval.

## Historical result (superseded)

These records describe source commit `b9bb526`, before the probe added an
explicit stdout flush. They do not attest the current probe source. The hosts
also resolved rustc 1.95.0 and 1.97.1 rather than the workspace's pinned 1.93.1,
so their workspace gates do not attest the pinned toolchain. A replacement
record must use the current exact-source and pinned-toolchain gates before it is
promoted.

- [Arm exact-source record](b9bb526-arm.md)
- [`xxl` exact-source record](b9bb526-xxl.md)
- [Two-host comparison](b9bb526-comparison.md)
- [Raw archive hashes](raw/b9bb526/SHA256SUMS)
