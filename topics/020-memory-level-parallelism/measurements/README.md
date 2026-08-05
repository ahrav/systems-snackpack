# Measurements

Each host record names:

- the requested or configured endpoint, any runtime alias, and the resolved
  hostname;
- architecture, CPU evidence, kernel, selected CPU, sibling topology, and
  available CPU count;
- Rust toolchain, native build flags, source commit, source archive digest, and
  binary digest;
- node count, working-set bytes, useful loads, process count, order schedule,
  startup boundary, and run window;
- one- and eight-chain medians, paired point estimate, interval, dispersion, and
  A/A diagnostic;
- final-image code generation and PMU availability;
- measured facts, vendor evidence, and inferred mechanisms as separate claims.

Raw evidence lives below `raw/<source-prefix>/`. The cross-host note compares
exact runs without treating two hosts as instruction-set populations.

## 2026-07-30 records

- [Required AArch64 host](2026-07-30-arm.md)
- [Configured live x86 host](2026-07-30-x86-live.md)
- [Cross-host comparison](2026-07-30-cross-host.md)
- [Rejected source candidate](2026-07-30-failed-candidate.md)
- [Local smoke](2026-07-30-local-smoke.md)

The instructed second endpoint,
`dev-dsk-ahrav-2c-b89a08b3.us-west-2.amazon.com`, returned WSSH 403. The x86
record is from the configured `xxl` alias, which resolved to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. It is retained as replacement
evidence and is not represented as a successful run on the unreachable literal
endpoint.
