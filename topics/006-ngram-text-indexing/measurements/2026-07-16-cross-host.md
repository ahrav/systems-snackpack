# Cross-host observations — 2026-07-16

Both hosts ran source commit
`e3442c23f06ef9c060f869574f532caef46fd04a`, the same 6 MiB corpus, the same
320 queries, and the same balanced schedule. Both exact oracles passed and both
hosts produced the same result hashes and candidate counts.

| Observation | dev-dsk-2b | dev-dsk-2c |
|---|---:|---:|
| Architecture and exposed CPU | AArch64, Arm part `0xd40` r1p1 | x86-64, AMD EPYC 9R14 under KVM |
| Available CPUs | 64 | 48 |
| Selective paired speedup | 282.253x `[278.818, 285.365]` | 179.600x `[158.936, 199.888]` |
| Common workload | median 2.460% index overhead | order reversal; no stable pooled effect |
| Index build median | 629.885 ms | 648.304 ms |
| Data-generation median | 9.276 ms | 13.292 ms |

The values are elapsed-time observations for two particular hosts. They do not
form an ISA or vendor comparison. Architecture, CPU, virtualization, kernel,
and generated binary differ. The measured common-workload order reversal on
dev-dsk-2c also prevents treating its pooled common ratio as a steady-state
effect.

The focused generated-code inspection found the same structure: scalar
document and first-byte loops, followed by a dynamic `bcmp` call after a
first-byte hit. No explicit vector-register instruction appeared in the three
focused functions on either host, although vector code existed elsewhere in
each compilation unit. This is observed compiler output. Any vectorization
inside libc's selected `bcmp`, and any causal explanation for the timing
differences, remain unmeasured.
