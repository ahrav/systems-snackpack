# Cross-host observations — 2026-07-16

Both hosts ran source commit
`b2fb45158eeb2362499d09e40affce50d629c277`, the same 6 MiB corpus, the same
320 queries, and the same balanced schedule. Both exact oracles passed and both
hosts produced the same result hashes and candidate counts.

| Observation | dev-dsk-2b | dev-dsk-2c |
|---|---:|---:|
| Architecture and exposed CPU | AArch64, Arm part `0xd40` r1p1 | x86-64, AMD EPYC 9R14 under KVM |
| Available CPUs | 64 | 48 |
| Selective paired speedup | 327.275x `[315.143, 335.273]` | 163.365x `[158.727, 199.093]` |
| Common workload | median 3.495% index overhead | order reversal; no stable pooled effect |
| Index build median | 636.061 ms | 651.798 ms |
| Data-generation median | 9.548 ms | 13.295 ms |

The values are elapsed-time observations for two particular hosts. They do not
form an ISA or vendor comparison. Architecture, CPU, virtualization, kernel,
and generated binary differ. The measured common-workload order reversal on
dev-dsk-2c also prevents treating its pooled common ratio as a steady-state
effect.

The focused generated-code inspection found the same structure: scalar
document and first-byte loops, followed by a dynamic `bcmp` call after a
first-byte hit. This is observed compiler output. Any vectorization inside
libc's selected `bcmp`, and any causal explanation for the timing differences,
remain unmeasured.
