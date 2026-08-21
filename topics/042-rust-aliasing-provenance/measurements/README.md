# Topic 42 measurement contract

This topic retains deterministic correctness and generated-code evidence. It
does not report elapsed time or rank processors.

Each required Linux host builds the same digest-checked Git archive. Eight
fresh processes must match [`../experiment/expected.txt`](../experiment/expected.txt)
exactly without retry. The receipts bind the program output, compiler and LLVM
versions, build flags, CPU and kernel identity, optimized LLVM intermediate
representation, native assembly, object code, and linked executable to that
source.

The LLVM check distinguishes a reference contract that forbids overlap from a
raw-pointer contract that permits exact overlap. Native instruction sequences
are recorded for the two named hosts but are not generalized to an instruction
set architecture, processor vendor, or other compiler version.

Each host note maps its numbers and generated-code statements to named records
inside the sealed archive. The cross-host note compares only fields retained by
both archives. It labels contract explanations as inferred rather than
measured.

[`../rounds/01.md`](../rounds/01.md) defines the acceptance contract. The first
retained run passed on both required hosts:

- [`2026-08-21-arm.md`](2026-08-21-arm.md)
- [`2026-08-21-xxl.md`](2026-08-21-xxl.md)
- [`2026-08-21-comparison.md`](2026-08-21-comparison.md)

The sealed bundles and source identity are under
[`raw/2026-08-21-af126fa/`](raw/2026-08-21-af126fa/).
