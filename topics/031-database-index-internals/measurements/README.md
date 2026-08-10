# Measurement contract

This topic compares one narrow-index-plus-payload layout with one wider
covering layout. Both are deterministic in-memory Rust representations.

## Required records

Each promoted host record names:

- source commit and shared source-archive Secure Hash Algorithm 256-bit
  (SHA-256) digest;
- Secure Shell (SSH) target, resolved hostname, architecture, kernel, central
  processing unit (CPU) identity, and available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, target features, and exact
  build flags;
- 48 fresh-process results for each retained build, with twelve complete
  paired blocks and 24 observations per treatment;
- correctness-oracle outcome, per-process checksums, logical byte counts, and
  Rust layout sizes;
- setup, nonsteady, and steady timing kept as separate fields;
- paired point estimate, block dispersion, order strata, and interval method;
- binary hashes, exported inspection symbols, and linked disassembly;
- all workspace-gate outcomes; and
- before-and-after source manifests proving unchanged source bytes.

## Interpretation

The point estimate compares treatments within complete blocks on one host. The
interval covers block-to-block variation during that run window. It does not
cover other hosts, compiler builds, page sizes, data distributions, database
engines, or storage systems.

Elapsed time is measured. Generated instructions and data layouts are observed.
Cache behavior is inferred from those observations unless hardware counters
are collected and reported. No result may be generalized from one host to its
instruction-set architecture or processor family.

Raw logs are retained as one compressed archive per required host. An outer
`SHA256SUMS` checksum manifest verifies each archive after retrieval. Host and
comparison notes are added only after exact-source runs pass this contract.

## Retained exact-source result

The following records cover source commit
`e88c3633d6a12b9787c31ec0612bccd810d5533d`. Later documentation commits do not
change what those records attest.

- [Required Arm host](e88c363-arm.md)
- [Runtime-resolved `xxl` host](e88c363-xxl.md)
- [Two-host comparison](e88c363-comparison.md)
- [Raw archive hashes](raw/e88c363/SHA256SUMS)
