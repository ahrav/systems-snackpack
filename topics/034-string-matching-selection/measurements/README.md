# Measurement contract

This topic retains correctness, elapsed-time, process-order, and generated-code
evidence for three source-defined exact byte matchers.

## Required records

Each promoted host record names:

- the source commit and shared source-archive Secure Hash Algorithm 256-bit
  (SHA-256) digest;
- the Secure Shell (SSH) target, resolved hostname, architecture, kernel,
  central processing unit (CPU) identity, and available CPU count;
- Rust, Cargo, C compiler, binary-tools versions, reported target features,
  build flags, affinity, and binary digest;
- generic and native correctness outcomes;
- the frozen repetition map and deterministic schedule;
- every raw process row, exit status, and external wall time;
- 12 complete-block contrasts per candidate-versus-baseline family, case, and
  mode;
- four same-method schedule-check blocks, kept separate from those families;
- independent receipt-validation output; and
- linked symbols and disassembly for all three matchers.

## Interpretation

Elapsed time measures the exact executable, input, host, affinity, and run
window. The complete-block ratio compares methods inside that window. Its sample
standard deviation covers variation among complete block contrasts, not other
machines, compiler versions, corpora, or future runs. Inner repetitions do not
increase the independent run count.

Generated instructions establish linked code shape only. They do not prove
that one instruction caused a timing difference or that another compiler emits
the same shape. Host CPU model and feature flags are vendor evidence, not a
license to generalize the timing to an instruction-set architecture or vendor
family.

The probe's logical throughput counts bytes presented to the search API. It is
not physical memory traffic or memory bandwidth. The deterministic synthetic
cases expose mechanisms and traps; they do not represent a production workload
distribution.

Raw logs are stored as one compressed archive per required host. An outer
`SHA256SUMS` file verifies each retrieved archive.

## Retained exact-source result

Source commit `b8d7f88a25aede60fb589099239c771285450293` passed on both
required hosts:

- [Arm exact-source record](b8d7f88-arm.md)
- [`xxl` exact-source record](b8d7f88-xxl.md)
- [Two-host comparison](b8d7f88-comparison.md)
- [Raw archive hashes](raw/b8d7f88/SHA256SUMS)
