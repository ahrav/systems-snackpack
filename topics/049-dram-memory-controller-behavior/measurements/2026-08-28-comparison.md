# Cross-host evidence boundary: 2026-08-28

Both exact hosts showed a loaded-treatment increase in the large dependent
chain while the earlier small control and loaded/loaded A/A paths remained
centered near one. The magnitude belongs only to these hosts, binaries,
placements, schedules, and run windows.

| Observation | Required AArch64 host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Idle median large-chain ns/load | 140.436 | 161.288 |
| Loaded median large-chain ns/load | 198.965 | 174.857 |
| Loaded/idle ratio | 1.417803 | 1.083771 |
| 95% between-block interval | 1.413943-1.421674 | 1.082705-1.084838 |
| Loaded/idle small-control ratio | 1.003146 | 1.001609 |
| Loaded-path B/A A/A ratio | 0.998369 | 1.000293 |
| Median useful-source lower bound, GiB/s | 133.912643 | 77.759694 |

This is not an Arm-versus-x86 benchmark. The hosts differ in processor,
virtualization, topology, memory system, kernel, and generated stream code.
The Arm stream used SVE; the x86 stream used 256-bit vectors. One ratio cannot
establish an instruction-set or vendor rule.

Measured facts are elapsed times, useful-source bounds, resource counters,
affinity canaries, mapping observations, checksums, host settings, and linked
instructions. Ratios and intervals are derived from complete process blocks.
Concurrent workers plausibly increased pressure somewhere in the shared memory
hierarchy. DRAM-only latency, row-buffer state, controller saturation, queue
policy, channel mapping, and refresh remain unmeasured because neither guest
exposed a controller PMU and no physical bank or row mapping was recovered.

The first full Arm campaign is preserved but rejected because its final period
failed the fault and scheduler canaries. No estimate from that campaign is
mixed with the complete retry.
