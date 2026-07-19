# Cross-host measurement boundary, 2026-07-19

Both hosts used source candidate `4e855a3` and recorded the same minimized
source-archive digest and identical per-file source hashes. Both used native
target selection, a `2^26`-bit deterministic input, 4,000,000 queries per
variant, and 12 fresh order-balanced paired processes. Their kernels shared the
6.12.94 Amazon Linux version family. Their CPUs, toolchains, binaries, and host
topology differed.

## Observations

| Comparison | Arm host | `xlg` |
| --- | ---: | ---: |
| Compact median | 12.861 ns/query | 5.124 ns/query |
| Prefix median | 10.951 ns/query | 8.384 ns/query |
| Paired prefix/compact median | 0.850 | 1.641 |
| Exact 96.1% interval | 0.815 to 0.902 | 1.399 to 1.709 |
| Compact first/second median | 12.319 / 13.435 | 5.003 / 5.616 |

The structural result was identical: the prefix/compact logical-byte ratio was
24.381. The timing result was not. The prefix oracle was
faster on the Arm host, while the compact directory was faster on `xlg`.

Linked code on both hosts retained bounds checks and three indexed data loads
for the compact query versus one indexed load for the prefix query. The
population count lowered to SVE `cnt` on the Arm host and `popcnt` on `xlg`.
These are binary observations, not explanations for the timing difference.

Both hosts showed a material order effect for the compact loop. The paired,
order-balanced protocol covers that variation. It does not identify whether
the cause was cache state, frequency, memory-system state, or another process
interaction. No PMU run was recorded.

The two hosts are not samples of an ISA, CPU vendor, hypervisor, or kernel-wide
effect. The experiment establishes only that representation size did not by
itself predict query latency on these exact systems.

Evidence roots:

- [Arm host](raw/4e855a3/dev-dsk-ahrav-2b/)
- [`xlg`](raw/4e855a3/xlg/)
- [SHA-256 manifest](raw/4e855a3/SHA256SUMS)
