# Cross-host comparison: 2026-08-26

Both hosts support the same lesson conclusion: a correct atomic counter remains
a serialized meeting point, CAS adds observable retry work, and changing the
representation can remove most meetings. The magnitude belongs to these two
hosts and this fixed workload.

| Observation | AArch64 host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Shared median steady ns/update | 8.708 | 22.226 |
| CAS/shared paired ratio | 1.684 | 1.670 |
| Median failed CAS attempts/success | 0.329 | 0.583 |
| Striped/shared paired ratio | 0.0800 | 0.0428 |
| Batched/shared paired ratio | 0.0199 | 0.0101 |
| A/A paired ratio | 0.971 | 1.028 |

The table is not an Arm-versus-x86 benchmark. The machines differ in processor,
virtualization, topology, kernel, compiler revision, and clock behavior. The
design also compares different interfaces: stripes require aggregation, and
batches delay visibility. The direct cross-host evidence is limited to the
named binaries, processors, placements, process schedules, and run windows.

Measured facts are elapsed phase times, final counts, software retries, exact
placement, hashes, and emitted instructions. Rust atomicity and ordering are
language guarantees. Writable-line arbitration and ownership movement explain
the result but remain inferred because this experiment collected no hardware
cache-to-cache events.
