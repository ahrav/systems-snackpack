# Cross-host correctness and code-generation comparison

Date: 2026-08-23

## What was compared

Both required Linux hosts consumed the same scoped Git archive from source
commit `b8d0c8b06bd29dab090d40f18aa6aa086b5fdf76`. The archive SHA-256
digest was
`ca305b96c2a34fc2e73ec6ef4dab2deb8586148bd69ccf4848f3f9a26d6daae1`.
Each host built with release optimization, native processor selection, and
abort-on-panic code generation. Each then launched eight independent processes.

This run did not compare elapsed time. The experiment uses a fixed four-bucket
workload, and timing would answer a different question from the
aggregation-correctness contract.

| Boundary | Arm host | `xxl` host |
| --- | --- | --- |
| Target | fixed literal host | alias resolved at run time |
| Hostname | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | `aarch64` | `x86_64` |
| Processor evidence | AWS c7g.16xlarge; Arm part `0xd40` | Intel Xeon Platinum 8488C, family 6 model 143 |
| Logical CPUs available to the process | 64 | 192 |
| Kernel | 6.12.100-125.179 | 6.12.95-124.187 |
| rustc and LLVM | 1.95.0, 22.1.2 | 1.97.1, 22.1.6 |
| Fresh processes | 8 of 8 passed | 8 of 8 passed |
| Receipt validator | passed on host and after retrieval | passed on host and after retrieval |

## Common observed result

All 16 processes produced byte-identical copies of the expected output. The two
local percentile values were 1 and 1,000 microseconds. Their union's exact p99
was 100 microseconds. The unweighted local-percentile mean was 500.5
microseconds, and the request-count-weighted mean was about 10.891 microseconds.
The compatible histogram conserved all 1,010 observations and bracketed p99 in
`(10, 100]`. The schema-mismatch and cumulative-reset controls both reported
`REJECTED`.

This is 16 correctness replications split across two named machines. It is not
16 performance samples, a statistical estimate of other machines, or evidence
that production telemetry is unbiased.

## Different observed lowering

Both compilers kept four checked additions ahead of all destination stores,
which matches the transactional source contract. The Arm build used `ldr`,
`adds`, and `b.hs`, followed by two paired `stp` stores. The x86-64 build used
`movq`, memory-source `addq`, and `jb`, followed by four `movq` stores.

The instruction sequences are measured generated-code observations. The shared
store-after-check structure is consistent with the source contract. Any claim
about why one compiler selected its exact instructions is an inference. No
speed, instruction-set, processor-family, or compiler-family conclusion follows.

## Evidence boundary

- **Measured:** host and toolchain identities, exact output, process count,
  executable and source digests, tests, build status, source stability,
  generated files, symbols, and validator results.
- **Derived:** nearest-rank position 1,000 for p99 of 1,010 observations, the two
  invalid averages, and four checked additions in this merge example.
- **Inferred:** local percentile scalars fail because they discard cross-shard
  ordering, while equal-schema count addition preserves the union in bucket
  space.
- **Not established:** production representativeness, sampling independence,
  sketch-library accuracy, telemetry loss, coordinated omission, elapsed time,
  throughput, or other hosts and compiler versions.

See the [Arm note](2026-08-23-arm.md), the [`xxl` note](2026-08-23-xxl.md), and
the [raw evidence](raw/2026-08-23-b8d0c8b/).
