# Measurement contract

This topic retains correctness and generated-code evidence. It reports no
timing comparison.

## Required records

A generic build uses the compiler's baseline target features. A native build
permits the target features reported by that host. Linked disassembly is the
machine-instruction listing from the final executable. Each promoted host
record names:

- source commit and shared source-archive Secure Hash Algorithm 256-bit
  (SHA-256) digest;
- Secure Shell (SSH) target, resolved hostname, architecture, kernel, central
  processing unit (CPU) identity, and available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, native target features, and
  exact build flags;
- eight generic and eight native fresh-process receipts;
- independent receipt validation for both builds;
- retained binary hashes, exported inspection symbols, and linked disassembly;
- all workspace-gate outcomes; and
- before-and-after source manifests that prove unchanged source bytes.

## Interpretation

Matching output establishes expected-output conformance for the retained
source, compilers, binaries, hosts, and run windows. It does not establish the
model's correctness or validate PostgreSQL 18 or another database
implementation.

Generated instructions establish code shape only. They do not prove that a
path executed or that PostgreSQL emits similar instructions. Do not generalize
one host's result to its instruction-set architecture, processor vendor, or
model family.

Raw logs are retained as one compressed archive per required host. An outer
`SHA256SUMS` file verifies each archive after retrieval.

## Retained exact-source result

No exact-source result has been promoted yet.
