# Topic 49 measurement records

The 2026-08-28 first visit passed on both required Linux targets:

- [AArch64 host result](2026-08-28-arm.md) — accepted from a complete retry;
  the first fixed-horizon Arm campaign was rejected as a whole
- [`xxl` host result](2026-08-28-xxl.md)
- [cross-host comparison](2026-08-28-comparison.md)

Both accepted campaigns use source commit
`8ad95023e53c516499c1c85631582c52ebd63921` and one path-limited source
archive. Each contains 12 primary four-process blocks and four A/A blocks: 64
fresh process identifiers, no replacement attempts, and process-level rather
than inner-loop replication.

Worker rates cover the full run epoch from release through worker join. They
bound application useful source bytes, not cache, fabric, integrated memory
controller (IMC), or dynamic random-access memory (DRAM) traffic. Resource
counters around the large walk are reported both process-wide and for the
probe thread. Every accepted process recorded zero minor and major faults in
both scopes.

The immutable receipts, the rejected first Arm campaign, controller-side
validations, and outer checksums are under
[`raw/2026-08-28-8ad9502/`](raw/2026-08-28-8ad9502/).
