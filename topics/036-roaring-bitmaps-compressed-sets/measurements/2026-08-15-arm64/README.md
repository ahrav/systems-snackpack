# Arm exact-source receipt

This record covers the literal required host
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` on 2026-08-15 UTC. The host
reported AArch64, Linux 6.12.95-124.187.amzn2023.aarch64, ARM model 1 r1p1,
64 available CPUs, one NUMA node, and SVE support. The build used rustc 1.95.0
with LLVM 22.1.2 and `-C target-cpu=native -C debuginfo=1`.

The source archive SHA-256 was
`43919a031a53d6ddef976d7e2ec4bf55fed565984c79181568925b01d83230a1`.
The native binary SHA-256 was
`68360fac281a684489e6728eb45e65eb088751736ead0731d278525d9c6f46fa`.
Generic and native correctness probes passed all five cases.

Each estimate is the median candidate/bitmap elapsed-time ratio from 12 paired,
order-balanced fresh-process blocks. The brackets contain the inclusive
interquartile range across those block ratios.

| Case | Median [IQR] |
| --- | ---: |
| `tiny16` array/bitmap | 0.151670505 [0.151076804, 0.153327777] |
| `sparse256` array/bitmap | 2.422791478 [2.421387675, 2.428848938] |
| `threshold4096` array/bitmap | 37.730651404 [37.615466572, 37.812116275] |
| `dense32768` array/bitmap | 196.660606170 [196.532671710, 197.240854791] |
| `runs64` run/bitmap | 2.520290876 [2.518226871, 2.523743425] |
| bitmap/bitmap A/A, four blocks | 1.000740707 [1.000093298, 1.001148512] |

The linked bitmap kernel used SVE `z` registers with vector loads, AND, `cnt`,
and `uaddv`. The array and run kernels remained scalar. This code shape was
observed; its causal contribution was not isolated.

`benchmark.txt` retains all 128 timed child rows and summary rows. `host.txt`,
`SHA256SUMS.txt`, `verify-*.txt`, `symbols.txt`, and `codegen.txt` retain the
measurement boundary.
