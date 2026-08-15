# x86-64 exact-source receipt

The required SSH alias `xxl` resolved during this run to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. The host independently
reported x86-64, Linux 6.12.95-124.187.amzn2023.x86_64, an Intel Xeon Platinum
8488C, 192 available CPUs, two NUMA nodes, and AVX2 plus AVX-512 VPOPCNTDQ.
The build used rustc 1.97.1 with LLVM 22.1.6 and
`-C target-cpu=native -C debuginfo=1`.

The source archive SHA-256 was
`43919a031a53d6ddef976d7e2ec4bf55fed565984c79181568925b01d83230a1`.
The native binary SHA-256 was
`94c2b36364ffe98566b68a4567e937b0e7cdd332afc2a857929a0daa956d7ebf`.
Generic and native correctness probes passed all five cases.

Each estimate is the median candidate/bitmap elapsed-time ratio from 12 paired,
order-balanced fresh-process blocks. The brackets contain the inclusive
interquartile range across those block ratios.

| Case | Median [IQR] |
| --- | ---: |
| `tiny16` array/bitmap | 0.196955641 [0.196794020, 0.197091033] |
| `sparse256` array/bitmap | 3.075839376 [3.072346450, 3.083156901] |
| `threshold4096` array/bitmap | 47.486844057 [47.342032453, 48.105404568] |
| `dense32768` array/bitmap | 310.111693569 [307.208858259, 312.259022479] |
| `runs64` run/bitmap | 2.878707445 [2.870126234, 2.892766912] |
| bitmap/bitmap A/A, four blocks | 0.998624744 [0.997412161, 1.003285833] |

The linked bitmap kernel used 256-bit `vpand` and AVX-512 VPOPCNTDQ
`vpopcntq`. The array and run kernels remained scalar. This code shape was
observed; its causal contribution was not isolated.

`benchmark.txt` retains all 128 timed child rows and summary rows. `host.txt`,
`SHA256SUMS.txt`, `verify-*.txt`, `symbols.txt`, and `codegen.txt` retain the
measurement boundary.
