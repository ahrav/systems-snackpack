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
