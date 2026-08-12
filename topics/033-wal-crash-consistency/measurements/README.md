# Measurement contract

This topic retains one correctness experiment, one process-crash experiment,
and one focused group-commit timing comparison.

## Required records

Each promoted host record names:

- source commit and shared source-archive SHA-256;
- SSH target, resolved hostname, architecture, kernel, CPU model, available CPU
  count, filesystem, mount options, and visible block-device identity;
- Rust, Cargo, C compiler, binary-tools versions, target features, and generic
  or native build flags;
- deterministic model and external-supervisor process-crash outputs for generic
  and native builds;
- eight ABBA/BAAB-balanced blocks from the native binary, preserving all 32
  fresh-process rows and separate I/O, process, and recovery durations;
- an independent raw-row validation and recomputed B/A estimate;
- final binary hashes, exported symbols, and disassembly;
- workspace-gate outcomes; and
- before/after source manifests proving that the run did not rewrite source.

## Interpretation

The model validates framing and prefix-recovery rules. The `SIGKILL` checks
validate a process-crash oracle while the kernel remains live. Neither is a
power-cut test.

The timing estimate compares 16 durability calls with 128 durability calls for
one 37,888-byte log workload. It describes the exact source, binary, host,
filesystem, device presentation, load, and run window. It does not estimate a
database's group-commit latency or generalize to an instruction-set
architecture, processor vendor, storage family, or physical power-loss
contract.

Raw logs are retained as one compressed archive per host. An outer
`SHA256SUMS` file verifies the archives after retrieval.
