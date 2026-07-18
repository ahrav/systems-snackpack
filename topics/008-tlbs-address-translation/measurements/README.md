# Measurement records

Each dated host record identifies the exact source candidate, resolved host,
kernel, CPU model, toolchain, target flags, mapping evidence, process count,
timing boundary, and generated code. Raw logs live under
`raw/<source-commit>/<host>/` with SHA-256 checksums.

The reach comparison requires 12 fresh, paired, order-balanced processes for
each mapping. Every base process must report zero `AnonHugePages`; every THP
process must report the complete mapping as `AnonHugePages` both before and
after timing.

The permission-change comparison also uses 12 fresh, paired, order-balanced
processes. It measures two `mprotect` calls per pair plus page-table work,
scheduling, invalidation, and completion. It does not isolate TLB shootdown or
interprocessor-interrupt latency.

Cross-host notes compare observations. They do not treat two guest machines as
samples of an instruction set, CPU vendor, or bare-metal platform.
