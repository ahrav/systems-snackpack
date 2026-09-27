# LSM trees and compaction economics

This crate checks two contracts: version reclamation must preserve reads, and
compaction accounting must count both input reads and output writes.

`compact` models one key with point values and deletion markers. It keeps every
version above the oldest snapshot plus the first version at or below it. Removing
a boundary tombstone also requires complete coverage of older values. The caller
must prove that coverage; a Boolean cannot discover it. Tests include a deliberate
resurrection counterexample and exhaustive modeled snapshot checks.

`Job` counts incoming, overlapping destination, and output transfer bytes.
`next_debt` models one interval of arrivals and available service, with surplus
service discarded. It uses widened arithmetic and rejects unrepresentable results.

```bash
cargo test -p lsm-compaction-economics
cargo run -p lsm-compaction-economics --example accounting
```

The example reports three pinned versions, one guarded tombstone, zero retained
versions with complete coverage, 608 MiB of transfer work, and 420 MiB of debt.
These are deterministic model results. There is no storage-engine throughput,
compression, persistence, range-delete, concurrent-publication, or crash-safety claim.

See [round 1](rounds/01.md), [sources](references.md), and the
[exact-source runner](experiment/run_host.sh).
