# Cross-host measurement boundary, 2026-07-20

Both hosts used source candidate `2ef0239`, source archive SHA-256
`3b0c06b53e402bf9bb74ac24da77e326419607f9f37af47b7ca3a78e45d91598`,
native target selection, the same deterministic 4,096-byte slice at offset 3,
and 12 fresh order-balanced process pairs. Both kernels shared the
6.12.94 Amazon Linux version family. Their CPUs, toolchains, binaries, and host
topologies differed.

## Observations

| Metric | Arm host | `xlg` |
| --- | ---: | ---: |
| Table median | 0.372011 GB/s | 0.462003 GB/s |
| Hardware median | 20.379436 GB/s | 10.111547 GB/s |
| Paired hardware speedup median | 54.830321x | 21.885901x |
| Paired-ratio MAD | 0.081290x | 0.010985x |
| Table-hardware stratum median | 54.845781x | 21.872383x |
| Hardware-table stratum median | 54.781672x | 21.891467x |

Both hosts produced CRC-32C `0xCF69B429` and digest
`0x9308E4DDC9CAC909` in every measured process. Both also passed the
independent oracle, standard-vector, fragmentation, and offset checks.

The linked Arm binary used `crc32cx` plus CRC32C tail instructions. The
linked x86-64 binary used `crc32q` plus CRC32 tail instructions. Both table
boundaries retained indexed 32-bit table loads. These are binary observations,
not an explanation for either ratio.

The experiment compares only a bytewise slice-by-one table with one dependent
hardware CRC chain. It does not measure polynomial folding, parallel streams,
I/O, or small-message dispatch cost. The absolute rates do not rank the
architectures: the hosts differ in CPU, virtualization, compiler, binary, and
system state. No PMU or frequency trace was recorded.

Evidence roots:

- [Arm host](raw/2ef0239/dev-dsk-ahrav-2b/)
- [`xlg`](raw/2ef0239/xlg/)
- [SHA-256 manifest](raw/2ef0239/SHA256SUMS)
