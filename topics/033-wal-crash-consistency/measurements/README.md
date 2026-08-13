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

The host runner reads Git's embedded commit identifier from the transferred
archive and requires it to match the recorded source commit. It records the
archive digest but does not copy the full repository archive into each host
receipt.

## Promoted result

- [Arm record](2c67633-arm.md)
- [`xxl` record](2c67633-xxl.md)
- [Cross-host comparison](2c67633-comparison.md)
- [Raw archive manifest](raw/2c67633/SHA256SUMS)

### Pre-hardening attestation scope

The promoted records ran the source of commit
`2c67633c2dbb7b5d56a247767d06293687e4827c`, which remains an ancestor of this
history. That runner and probe predate the review-driven hardening series:
loader and toolchain environment sweeps that run before any external command,
the `BASH_ENV` sanitizing re-exec, binding and hashing of every required tool
and of the rustup-dispatched `rustc`, `cargo`, `rustdoc`, `cargo-fmt`, and
`cargo-clippy`, refusal of ambient `.cargo`, rustfmt, and Clippy configs in
ancestor directories, verify-then-extract handling of a private archive copy,
the fail-closed tmpfs gate, hermetic (`-I -S`) receipt validation, the
probe's direct `SIGKILL` with waited-signal verification, and the recovery
check that rejects frames with nonzero flags or reserved header fields. Those
archives therefore contain no `environment.before.txt`,
`tool-provenance.txt`, or `toolchain-dispatch.txt`, do not attest the absence
of inherited environment state, and their measured binaries accept nonzero
flags that the current source rejects.

Everything else the records attest is unchanged: source commit and archive
digest, host and toolchain identity, build flags, binary hashes and
disassembly, gate outcomes, model and process-crash outputs, and the 32
retained fresh-process rows per host. A rerun under the current runner is
required before any record here can claim a swept and recorded measurement
environment.
