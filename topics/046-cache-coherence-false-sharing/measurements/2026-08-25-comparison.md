# Cross-host comparison, 2026-08-25

Both required Linux hosts ran the same sealed source, operation count, process
schedule, and CPU-index pair. Both selected processors were distinct physical
cores in one package, and both reported 64-byte coherence lines. Each host
retained 48 fresh processes with no invalid or replaced attempt.

| Observation | Arm `c7g.16xlarge` | `xxl` Intel Xeon 8488C |
|---|---:|---:|
| Packed/padded geometric-mean time ratio | 2.9770 | 5.4294 |
| Descriptive 95% block-bootstrap interval | [2.8985, 3.0598] | [5.1962, 5.6523] |
| Complete primary blocks | 8 | 8 |
| Log-contrast standard deviation | 0.04186 | 0.06481 |
| Padded A/A ratio | 1.00036 | 1.00720 |
| Padded A/A interval | [0.99969, 1.00103] | [0.99759, 1.01738] |
| Emitted atomic operation | `ldadd` | `lock incq` |
| `perf c2c` memory events | Unsupported | Unsupported |

Separating the counters reduced fixed-work time on both exact placements. The
`xxl` ratio was about 1.82 times the Arm ratio, but a ratio of ratios does not
isolate a mechanism. Processor models, compiler versions, virtual-machine
environments, atomic implementations, and unobserved coherence paths differ.
The result does not rank Arm against x86-64 and does not predict another machine.

The measured facts are elapsed times, layout offsets, affinity, source and
binary identity, and emitted instructions. The interpretation that the packed
layout adds coherence or shared-line service work is consistent with the
controlled intervention and established coherence rules. Ownership-handoff
counts, L1 migration, near-versus-far Arm routing, and a vendor-wide performance
difference remain unmeasured.
