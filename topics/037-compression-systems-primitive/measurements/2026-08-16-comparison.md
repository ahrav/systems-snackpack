# Cross-host comparison: 2026-08-16

Both hosts ran the same commit and source-archive digest. Every treatment used
the same 262,144 input bytes, codec calls, stored container, and frozen schedule.
The observations are paired within each host; the two hosts are not statistical
replicates of an architecture family.

## Stored bytes were host-independent

| Corpus and representation | Independent units | One batch | Independent / batch |
| --- | ---: | ---: | ---: |
| Structured LZ4 | 102,127 | 5,284 | 19.328 |
| Structured zstd | 101,652 | 1,642 | 61.907 |
| Pseudorandom LZ4 with raw fallback | 275,456 | 262,157 | 1.051 |
| Pseudorandom zstd with raw fallback | 275,456 | 262,157 | 1.051 |

The structured zstd compression ratio, defined as input bytes divided by
stored bytes, was 2.579 for independent units and 159.649 for the batch. The
pseudorandom codec candidates expanded, so the policy selected raw bytes. The
stored result still includes the common unit header; raw fallback prevents
codec-payload expansion, not container metadata.

## Unit-shape time ratios differed by host

Each entry is the geometric mean of 12 complete-block `batch / independent`
time-per-byte ratios. Below one favors batching. The sample standard deviation
(SD) of each log ratio describes dispersion across the 12 block contrasts.

| Host | Codec | Phase | Ratio | SD(log ratio) | Working-model interval |
| --- | --- | --- | ---: | ---: | ---: |
| xxl/x86-64 | zstd | encode | 0.014304 | 0.007510 | [0.014236, 0.014372] |
| xxl/x86-64 | zstd | decode | 0.014560 | 0.026093 | [0.014321, 0.014804] |
| Arm | zstd | encode | 0.014936 | 0.008571 | [0.014855, 0.015018] |
| Arm | zstd | decode | 0.016350 | 0.006958 | [0.016278, 0.016423] |
| xxl/x86-64 | LZ4 | encode | 0.138794 | 0.004533 | [0.138395, 0.139195] |
| xxl/x86-64 | LZ4 | decode | 0.238838 | 0.055707 | [0.230533, 0.247443] |
| Arm | LZ4 | encode | 0.101571 | 0.004192 | [0.101300, 0.101842] |
| Arm | LZ4 | decode | 0.414773 | 0.023070 | [0.408738, 0.420898] |

The reciprocal zstd ratios are derived speed factors of 69.91 and 68.68 for
x86 encode and decode, and 66.95 and 61.16 for Arm. These are not pure codec
speedups: the treatment jointly changes codec call count, 13-byte unit framing,
history reset, and raw-fallback decisions.

The working-model intervals assume independent, approximately normal block log
contrasts. Sequential blocks on a shared host do not establish those
assumptions. Raw contrasts and sample dispersion are retained; the intervals
do not predict another run or cover all reported cells simultaneously.

## Code generation and mechanism boundary

The x86-64 wrappers contain external `call` sites and the AArch64 wrappers
contain external `bl` sites for `ZSTD_compressCCtx`, `ZSTD_decompressDCtx`,
`ZSTD_findFrameCompressedSize`, `LZ4_compress_default`,
`LZ4_decompress_safe`, and `memcpy`. This is static inspection of linked
wrapper code. It does not reveal the shared libraries' internal instruction
paths or prove why elapsed time changed.

Stored bytes and elapsed times are measured. Process order, checksums, and host,
toolchain, and library identities are recorded evidence. Linked call sites are
observed code generation. Ratios and throughput are derived. Better history
reuse, fewer calls, and improved amortization are plausible mechanisms, but
this experiment does not isolate them. Do not generalize either host to an
instruction-set architecture or vendor family.
