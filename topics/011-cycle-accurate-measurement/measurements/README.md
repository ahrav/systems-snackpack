# Measurement boundary

A host record applies to one commit-bound source archive, benchmark binary,
host, and 12-process design. The runner builds only a temporary extraction of
the verified archive and removes it on exit. Each host directory retains
environment, correctness, workspace gates, counter probe, raw process output,
summary, pre-build source hashes, their post-build verification, binary hash,
and linked code generation.

A final record is complete only after the harness and record review establish
all of these conditions:

- `SOURCE_ARCHIVE` is an absolute gzip-compressed Git archive whose SHA-256 and
  embedded commit match the declared values;
- the build runs from the verified extraction with `CARGO_ENCODED_RUSTFLAGS`,
  `RUSTC_WRAPPER`, and `RUSTC_WORKSPACE_WRAPPER` cleared and the recorded native
  `RUSTFLAGS` applied;
- source is inventoried before Cargo runs, every build uses `--locked`, and the
  post-build source verification matches every inventoried file;
- portable conversion and recurrence checks pass;
- both probes start and end on CPU 0, advance at least once, and report no
  backward values;
- x86 endpoints use the RDTSCP/CPUID boundary, capture TSC_AUX, and report no
  TSC_AUX change; this supplements rather than replaces the CPU check;
- 12 distinct CPU-0-pinned processes complete in the fixed three-block ABBA
  schedule, six per timer order, with identical final checksums;
- every process reports all four batch sizes with zero rejected samples and
  retains all 500 requested raw values;
- raw minima and exact doubled medians reproduce every derived batch field;
- each 65,536-operation median reaches 200 times its timer's minimum positive
  probe delta as an empirical granularity guard, not an accuracy bound;
- workspace format, test, Clippy, benchmark-build, and rustdoc gates pass;
- separate symbol-bounded linked-code gates match the full selected counter
  sequence in `read_counter` and a multiplication in `dependent_chain`.

Raw records contain measured counter-tick and `CLOCK_MONOTONIC_RAW` batch
durations. Batch medians and per-operation fields derive from those samples.
Host summaries further derive reference-counter nanoseconds per operation from
each process's doubled median ticks and recorded frequency. The cross-host note
keeps measured values, derived values, and observed code generation separate
from inferred mechanisms. It does not treat two machines as an architecture
comparison.

## Recorded evidence

- [Corrected Arm host](2026-07-21-corrected-arm.md)
- [Corrected `xlg` alias and resolved hostname](2026-07-21-corrected-xlg.md)
- [Corrected cross-host boundary](2026-07-21-corrected-cross-host.md)
- [Corrected raw evidence checksums](raw/5117e64/SHA256SUMS)
- [Superseded candidate `4b00356`](superseded-4b00356.md)
- [Superseded Arm host record](2026-07-21-dev-dsk-ahrav-2b.md)
- [Superseded `xlg` record](2026-07-21-xlg.md)
- [Superseded cross-host boundary](2026-07-21-cross-host.md)
- [Superseded raw evidence checksums](raw/4b00356/SHA256SUMS)
