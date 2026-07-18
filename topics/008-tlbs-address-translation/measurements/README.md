# Measurement records

Each dated host record identifies the exact source candidate, resolved host,
kernel, CPU model, toolchain, target flags, mapping evidence, process count,
timing boundary, and generated code. Raw logs live under
`raw/<source-commit>/<host>/` with SHA-256 checksums.

The reach comparison requires 12 fresh, paired, order-balanced processes for
each mapping. Every base process must report zero `AnonHugePages`; every THP
process must report the complete mapping as `AnonHugePages` both before and
after timing.

The final source also repeats base-mapping construction in 200 fresh test
processes per host. Retained `PROT_NONE` padding must keep the aligned usable
range as an exact VMA in every process.

The permission-change comparison also uses 12 fresh, paired, order-balanced
processes. It measures two `mprotect` calls per pair plus page-table work,
scheduling, invalidation, and completion. It does not isolate TLB shootdown or
interprocessor-interrupt latency.

Cross-host notes compare observations. They do not treat two guest machines as
samples of an instruction set, CPU vendor, or bare-metal platform.

Recorded evidence:

- [Arm host, 2026-07-18](2026-07-18-dev-dsk-ahrav-2b.md)
- [`xlg`, 2026-07-18](2026-07-18-xlg.md)
- [Cross-host boundary](2026-07-18-cross-host.md)
- [Raw logs and checksums](raw/52e7959/)
