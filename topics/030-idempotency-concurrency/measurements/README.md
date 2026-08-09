# Measurement contract

This topic retains correctness and generated-code evidence. It reports no
timing comparison.

## Required records

Each promoted host record names:

- source commit and shared source-archive SHA-256;
- SSH target, resolved hostname, architecture, kernel, CPU identity, and
  available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, native target features, and
  build flags;
- eight generic and eight native fresh-process receipts;
- independent receipt validation for both builds;
- retained binary hashes, exported inspection symbols, and disassembly;
- all workspace-gate outcomes; and
- a before/after source manifest showing identical source bytes at both checks.

## Interpretation

Matching deterministic output establishes portability for the retained source,
compiler, binary, host, and run-window combinations. It does not validate a
database, network, storage device, external side effect, or processor-family
performance claim.

Raw logs are retained as one compressed archive per required host. The outer
`SHA256SUMS` verifies those archives after retrieval.

The compact archives omit the source snapshot. They retain each host's reported
snapshot hash, before-and-after source manifests, binaries, process receipts,
generated code, gate logs, and CPU identity. Their internal checksums were
regenerated and checked after compaction.

## Promoted result

- [Arm exact-source record](ad25198-arm.md)
- [`xxl` exact-source record](ad25198-xxl.md)
- [Two-host comparison](ad25198-comparison.md)
- [Raw archive hashes](raw/ad25198/SHA256SUMS)
