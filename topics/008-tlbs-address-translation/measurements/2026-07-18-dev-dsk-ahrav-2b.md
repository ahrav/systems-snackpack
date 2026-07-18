# Arm host measurement, 2026-07-18

## Source and host

- Source candidate: `52e7959c18e03869aacf2548b60198c72e52e2c0`
- Source archive SHA-256: `2da77211c70a818ab257bfb5d59cd6acd6e5642812476dd5362bc6add36b238a`
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
SOURCE_COMMIT=52e7959c18e03869aacf2548b60198c72e52e2c0 \
SOURCE_ARCHIVE_SHA256=2da77211c70a818ab257bfb5d59cd6acd6e5642812476dd5362bc6add36b238a \
HOST_ALIAS=dev-dsk-ahrav-2b \
./topics/008-tlbs-address-translation/experiment/run_processes.sh \
  /tmp/topic8-final-52e7959-arm/results
```

The runner passed the workspace format, test, doc-test, clippy, benchmark-build,
and rustdoc gates. The recorded example and benchmark verification each
reported zero `AnonHugePages` plus `nh` for the base mapping, and full
`AnonHugePages` plus `hg` for the THP mapping.
Before the runner, 200 fresh test processes also passed the exact VMA-boundary
and page-ring check. The usable mapping was bounded by retained `PROT_NONE`
padding, so neighboring read-write VMAs could not coalesce with it.

## Process measurements

Each row has 12 fresh processes. Mean and sample standard deviation describe
process-to-process variation. Ratios are paired in alternating order. The
interval is the exact 96.1% distribution-free interval for the population
median of continuous, independent pair ratios, using order statistics 3 and
10 of 12.

| Timed region | Mean | SD | Paired median | Paired geometric mean | 96.1% median interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Reach, base | 130.704 ns/access | 1.203 ns/access |  |  |  |
| Reach, THP | 115.398 ns/access | 1.962 ns/access | 1.131 base/THP | 1.133 | 1.112 to 1.154 |
| Permission pair, 1 reader | 4.633 us/pair | 0.434 us/pair |  |  |  |
| Permission pair, 16 readers | 4.688 us/pair | 0.305 us/pair | 1.028 16/1 | 1.014 | 0.883 to 1.179 |

The reach timer covers 4,194,304 serial dependent loads after one full ring
traversal as warmup. It excludes mapping setup. The permission timer follows
100 warmup pairs and covers 20,000 complete read-only/read-write `mprotect`
pairs while pinned readers load the target page. It includes syscall,
page-table, scheduling, invalidation, acknowledgement, and reader-interference
costs.

Startup and steady state remain separate:

| Process | Setup mean ms (SD ms) | External mean ms (SD ms) |
| --- | ---: | ---: |
| Reach, base | 85.233 ms (5.273) | 669.376 ms (10.348) |
| Reach, THP | 8.778 ms (1.401) | 504.370 ms (8.768) |
| Permission, 1 reader | 0.868 ms (0.117) | 97.188 ms (8.612) |
| Permission, 16 readers | 2.055 ms (1.461) | 100.289 ms (6.950) |

External time begins before `taskset` launches the process and ends after it
exits. It includes launcher overhead, process startup, output, mapping teardown,
and exit. It is not a startup-only estimate.

## PMU and code generation

One descriptive 16-pass process per mapping produced these whole-process
counts. These are not replications and include setup and page faults.

| Mapping | Page faults | L1D TLB refill | L2D TLB refill | DTLB walk |
| --- | ---: | ---: | ---: | ---: |
| Base | 65,786 | 1,299,608 | 1,267,995 | 1,267,579 |
| THP | 376 | 839,586 | 938 | 654 |

LLVM emitted a four-load scalar dependency chain. Each step is an `lsl #12`
followed by an address-dependent `ldr`. There is no vectorization or independent
memory-level parallelism in the timed kernel.

Measured: THP reduced steady-state time for this workload, and the permission
ratio's interval includes 1. Inferred: the PMU change is consistent with fewer
lower-level translation walks after THP materialization. The counters do not
identify a TLB level's capacity or one invalidation mechanism.

Raw evidence: [`raw/52e7959/dev-dsk-ahrav-2b`](raw/52e7959/dev-dsk-ahrav-2b/).
