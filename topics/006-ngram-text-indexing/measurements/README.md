# Measurements

- [Apple M1 Pro smoke run, 2026-07-16](2026-07-16-m1-pro-smoke.md) records one
  process per method. It confirms exact-result hashes and the intended candidate
  counts; it does not estimate process-level variation.
- The Linux records will contain the exact host, toolchain, build flags, source
  and binary hashes, correctness result, 12 paired process runs, candidate counts,
  generated-code observation, and workspace-gate output.

Elapsed time, observed code generation, source-defined workload properties, and
inferred mechanisms remain separate. Cross-host differences do not establish an
instruction-set or vendor comparison.
