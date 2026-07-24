# Measurement records

A complete record set must contain one host note per required Linux target, a
cross-host comparison, and raw evidence under `raw/<source-prefix>/`.

Each host record must retain:

- requested and resolved hostname;
- architecture, `uname`, kernel, CPU vendor or implementer and model evidence,
  available CPU count, and affinity;
- Rust, Cargo, C compiler, binutils, target configuration, target features, and
  exact build flags;
- source commit, archive SHA-256, source-file hashes, and post-run source
  verification;
- every required workspace gate and the Topic 14 correctness example;
- release benchmark checksum, symbols, ELF header, focused disassembly, and
  compressed full linked disassembly;
- 72 raw process rows: three comparisons, 12 pairs with six in each order, and
  two arms per pair;
- setup, steady, verification, and external process intervals;
- per-arm medians, inclusive quartiles, sample standard deviations, ranges,
  throughput, and within-pair ratios;
- a SHA-256 manifest covering every retained file except the manifest itself.

The steady interval is the performance boundary. One pinned fresh process is
the replication unit. The eight passes within a process amortize timer and
startup costs but are not independent samples. The descriptive interquartile
range (IQR) covers variation among the 12 process observations or paired
process ratios in one run window. It is not a confidence interval for a CPU
family.

Setup includes allocation, deterministic fixture generation, scalar-oracle
evaluation, and any mode-specific pre-resolution. Verification follows the
steady interval. External wall time includes process startup and the runner;
subtracting the recorded internal phases leaves a mixed residual, not an
isolated startup measurement.

The scalar control is built with LLVM loop and superword-level parallelism
(SLP) vectorization disabled. The architecture-specific intrinsics remain
explicit. The crate baseline is `x86-64` on `x86_64` and `generic` on AArch64;
the recorded experiment does not use `target-cpu=native`.

Host notes and raw evidence are added only after the same committed archive
passes the full experiment on both required Linux hosts. A failure on either
host invalidates the topic completion gate.
