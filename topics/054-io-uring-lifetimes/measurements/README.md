# Measurement records

Topic 54 uses a correctness experiment, not a performance benchmark. The
accepted host records bind the exact committed source, archive, runner,
compiler, kernel, architecture, policy state, native binary, two process runs,
code generation, and independently validated sealed receipts.

No elapsed-time comparison is collected. Matching observations on two hosts do
not establish an instruction-set or vendor property.

## Source scope of the recorded runs

Both records bind native probe source
`ab7e2db7d0c73512f4a94c713976ed9722981323f88026b4d360b4193d4524d9`. The
checked-in probe has since diverged: it resumes an `EINTR`-interrupted
pre-check sleep instead of sampling readiness early, closing a false-pass
path in the deferred-progress oracle. The sealed receipts remain valid for
their recorded source but are superseded as evidence for the checked-in
probe. A new two-host collection is required to bind the current source.

- [Arm record](2026-09-02-arm.md)
- [`xxl` record](2026-09-02-xxl.md)
- [Exact-source comparison](2026-09-02-comparison.md)
