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

## Retained historical result

These records retain outputs for source commit
`ad2519824f2e309a287c9b7dc957bdd80eec86c9` only. They do not attest later
commits on this branch or the eventual merge or squash commit. The archives
also predate the current runner's loader sweep and `tool-provenance.txt` receipt.
Treat them as pre-protocol historical outputs, not proof that the current host
protocol ran. Regenerate them with the current runner before promotion under
this contract.

- [Arm historical host output](ad25198-arm.md)
- [`xxl` historical host output](ad25198-xxl.md)
- [Two-host comparison](ad25198-comparison.md)
- [Raw archive hashes](raw/ad25198/SHA256SUMS)
