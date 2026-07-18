# Arm host measurement, 2026-07-18

## Source and host

- Source candidate: `2a3b41216a3852d9fcf60c1e160eb379159f152f`
- Source archive SHA-256: `08f3f3acacf2cd8c5fac9d0a30505bdcb63f9c6f12c89c15a40a87ab12bdbcd0`
- Host label: `dev-dsk-ahrav-2b`
- Resolved host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Kernel: Linux `6.12.94-123.180.amzn2023.aarch64`
- `uname -a`: `Linux dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com 6.12.94-123.180.amzn2023.aarch64 #1 SMP Thu Jul  9 21:13:38 UTC 2026 aarch64 aarch64 aarch64 GNU/Linux`
- CPU evidence: `aarch64`, vendor `ARM`, model `1`, stepping `r1p1`, 64 online CPUs, one NUMA node
- Controller CPU: 0; reader CPUs: 1 through 16
- Toolchain: Rust 1.93.1, LLVM 21.1.8, GCC 11.5.0, perf 6.1.176-221.360
- Build flags: `-C target-cpu=native -C debuginfo=1 -C codegen-units=1`
- Page evidence: 4 KiB base pages, 2 MiB PMD THPs, THP and defrag policy `madvise`

From the extracted source archive, the exact run was:

```bash
SOURCE_COMMIT=2a3b41216a3852d9fcf60c1e160eb379159f152f \
SOURCE_ARCHIVE_SHA256=08f3f3acacf2cd8c5fac9d0a30505bdcb63f9c6f12c89c15a40a87ab12bdbcd0 \
HOST_ALIAS=dev-dsk-ahrav-2b \
./topics/008-tlbs-address-translation/experiment/run_processes.sh \
  /tmp/topic8-final-2a3b412.Fao4Bf/results
```

The runner passed the workspace format, test, doc-test, clippy, benchmark-build,
and rustdoc gates. The recorded example and benchmark verification each
reported zero `AnonHugePages` plus `nh` for the base mapping, and full
`AnonHugePages` plus `hg` for the THP mapping.

## Process measurements

Each row has 12 fresh processes. Mean and sample standard deviation describe
process-to-process variation. Ratios are paired in alternating order. The
interval is the exact 96.1% distribution-free interval for the population
median of continuous, independent pair ratios, using order statistics 3 and
10 of 12.

| Timed region | Mean | SD | Paired median | Paired geometric mean | 96.1% median interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reach, base | 129.831 ns/access | 1.452 ns/access |  |  |  |
| Reach, THP | 116.508 ns/access | 2.579 ns/access | 1.119 base/THP | 1.115 | 1.091 to 1.141 |
| Permission pair, 1 reader | 4.866 us/pair | 0.597 us/pair |  |  |  |
| Permission pair, 16 readers | 5.454 us/pair | 0.357 us/pair | 1.119 16/1 | 1.127 | 0.949 to 1.310 |

The reach timer covers 4,194,304 serial dependent loads after one full ring
traversal as warmup. It excludes mapping setup. The permission timer follows
100 warmup pairs and covers 20,000 complete read-only/read-write `mprotect`
pairs while pinned readers load the target page. It includes syscall,
page-table, scheduling, invalidation, acknowledgement, and reader-interference
costs.

Startup and steady state remain separate:

| Process | Setup mean ms (SD ms) | External mean ms (SD ms) |
| --- | ---: | ---: |
| Reach, base | 84.750 ms (4.884) | 667.194 ms (12.009) |
| Reach, THP | 9.060 ms (1.182) | 509.006 ms (11.513) |
| Permission, 1 reader | 0.846 ms (0.066) | 101.796 ms (11.942) |
| Permission, 16 readers | 2.363 ms (2.499) | 115.880 ms (7.250) |

External time begins before `taskset` launches the process and ends after it
exits. It includes launcher overhead, process startup, output, mapping teardown,
and exit. It is not a startup-only estimate.

## PMU and code generation

One descriptive 16-pass process per mapping produced these whole-process
counts. These are not replications and include setup and page faults.

| Mapping | Page faults | L1D TLB refill | L2D TLB refill | DTLB walk |
| --- | ---: | ---: | ---: | ---: |
| Base | 65,791 | 1,274,246 | 1,247,166 | 1,246,763 |
| THP | 383 | 839,520 | 966 | 686 |

LLVM emitted a four-load scalar dependency chain. Each step is an `lsl #12`
followed by an address-dependent `ldr`. There is no vectorization or independent
memory-level parallelism in the timed kernel.

Measured: THP reduced steady-state time for this workload, and the permission
ratio's interval includes 1. Inferred: the PMU change is consistent with fewer
lower-level translation walks after THP materialization. The counters do not
identify a TLB level's capacity or one invalidation mechanism.

Raw evidence: [`raw/2a3b412/dev-dsk-ahrav-2b`](raw/2a3b412/dev-dsk-ahrav-2b/).
