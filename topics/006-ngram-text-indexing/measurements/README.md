# Measurements

- [Apple M1 Pro smoke run, 2026-07-16](2026-07-16-m1-pro-smoke.md) records one
  process per method. It confirms exact-result hashes and the intended candidate
  counts; it does not estimate process-level variation.
- [dev-dsk-2b Linux run, 2026-07-16](2026-07-16-dev-dsk-2b.md) records 12
  balanced process pairs on the probed AArch64 host at final source `e3442c2`.
- [dev-dsk-2c Linux run, 2026-07-16](2026-07-16-dev-dsk-2c.md) records 12
  balanced process pairs on the probed x86-64 host at final source `e3442c2`
  and the measured workload-order reversal.
- [Cross-host observations](2026-07-16-cross-host.md) separate common evidence
  from host-specific results and inferences.
- [Raw Linux evidence](raw/) retains both the initial run and the exact final
  source rerun: environment, commands, every process result, correctness output,
  generated-code captures, and compressed full assembly.

Elapsed time, observed code generation, source-defined workload properties, and
inferred mechanisms remain separate. Cross-host differences do not establish an
instruction-set or vendor comparison.
