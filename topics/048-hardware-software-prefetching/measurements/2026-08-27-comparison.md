# Cross-host comparison: 2026-08-27

No tested explicit-prefetch candidate established an improvement on both
required hosts. All five randomized distances took longer on the exact
AArch64 host.
The runtime-resolved `xxl` host had two slower distances and three inconclusive
distances. The sequential distance-16 hint was inconclusive on the AArch64 host
and 47.392% slower on `xxl`.

Both runs used source commit
`43ba2249e862193a6b68fc5e4e72f06a377d40ef` and source archive SHA-256
`07f941a479b51e2af8d57fc23d80b5ddec78ce2d9cd4af0d73474c84d6cd3f9b`.
The executed C source and runner were byte-identical across hosts. Each host ran
104 fresh measured processes: 88 for randomized access and 16 for the
sequential control.

## Randomized gather

The table reports geometric-mean `B/A` ratios. In distance rows, `B` is the
explicit hint, so values above 1 mean the hint took longer. Both labels are
demand-only in the A/A row. Parentheses contain descriptive two-sided 95%
Student-t intervals over complete-block log ratios.

| Distance | Literal AArch64 host | Runtime-resolved `xxl` host |
|---:|---:|---:|
| 4 | 1.040998 (1.038283-1.043720) | 1.024206 (0.974031-1.076965) |
| 8 | 1.014106 (1.012814-1.015400) | 1.047161 (1.026554-1.068182) |
| 16 | 1.007521 (1.003864-1.011192) | 1.021027 (1.017802-1.024263) |
| 32 | 1.041438 (1.034522-1.048401) | 0.985492 (0.940304-1.032852) |
| 64 | 1.038488 (1.036641-1.040337) | 0.976087 (0.938818-1.014835) |
| A/A | 0.998738 (0.990859-1.006679) | 0.999635 (0.789825-1.265178) |

The `xxl` point estimates at distances 32 and 64 do not establish an
improvement because both intervals include 1. The wider `xxl` intervals also
show more complete-block variation in this run window. These observations do
not transfer to other processors, virtual machines, compiler versions, or
prefetch configurations.

## Sequential control

| Observation | Literal AArch64 host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Distance-16 prefetch/demand | 1.027342 (0.989837-1.066268) | 1.473923 (1.269000-1.711938) |
| A/A | 0.998092 (0.980052-1.016464) | 1.002141 (0.981445-1.023274) |
| Median initialization ms | 88.254579 | 102.382448 |
| Median warmup ms | 9.986955 | 25.440434 |
| Median timed ms | 19.996517 | 50.088830 |

Regular sequential access is a pattern that hardware prefetchers can recognize,
but this experiment did not count hardware-prefetch requests. Hardware
coverage, explicit-hint instruction cost, cache pollution, and bandwidth
pressure remain possible explanations, not measured causes.

## Host and code differences

| Identity | Literal AArch64 host | Runtime-resolved `xxl` host |
|---|---|---|
| Host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | `aarch64` | `x86_64` |
| Processor evidence | `MIDR_EL1=0x00000000411fd401` | Intel Xeon Platinum 8488C, family 6, model 143, stepping 8, microcode `0x2b000670` |
| Kernel | `6.12.100-125.179.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| Capacity | 64 processors, one socket, one thread/core | 192 processors, two sockets, two threads/core |
| GCC native target | `armv8.4-a+crypto+sha3+sm4+sve+rng+i8mm+bf16` | `sapphirerapids` |
| Binary SHA-256 | `4744bb740338745b475759c70289d09e607cafea1dbf2bee2bab7f92bd7ecc01` | `a38c402cb2059cdba82865794e1c7b791e6c1bf6f6afc72063e0be5068fff947` |
| Explicit hint observed | `prfm pldl1strm, [x6]` | `prefetchnta (%rdi,%rcx,1)` |
| Random phase medians, init/warmup/timed ms | 126.757774 / 30.817238 / 61.413200 | 129.998739 / 53.401931 / 106.404115 |

The table is not an Arm-versus-x86 benchmark. The hosts differ in processor,
topology, virtualization evidence, kernel, and compiler output. Clock behavior
and co-runners were uncontrolled. Absolute elapsed-time differences therefore
belong to the named hosts and run windows.

## Evidence boundary and decision

Measured facts are elapsed phase times, successful checksums, fault counts,
processor placement, source and binary hashes, compiler identity, and emitted
instructions. The analyzer recomputed one contrast per complete block. It did
not treat loop accesses or the two timed passes as independent samples.

The likely memory-system explanations remain inferred because the campaign
recorded no model-specific performance-monitoring counters. The data does not
show whether hardware prefetchers recognized a stream, which cache served a
line, how many prefetched lines were useful, or whether bandwidth saturated.

The evidence supports one narrow decision: retain the demand-only kernel for
this exact candidate. It does not support a rule that software prefetch always
loses, or that either instruction-set architecture handles prefetching better.
The host details and full distributions are in
[`2026-08-27-arm.md`](2026-08-27-arm.md),
[`2026-08-27-xxl.md`](2026-08-27-xxl.md), and the
[`raw receipt index`](raw/2026-08-27-43ba224/README.md).
