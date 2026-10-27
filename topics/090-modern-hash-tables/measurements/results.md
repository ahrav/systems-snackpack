# Measured lookup results

Exact source: `b082d9b05a42fbf2fd9eb2723ba977fc424fa95c`.
Archive SHA-256: `102940306d76d9fdfd701688d9922146c589bcf635b53e9b0150602ce5c83133`.

All three machines used Rust 1.93.1 and the same committed source. Each ran
108 measured fresh processes and 18 warmups: six balanced blocks per workload.
Every query passed the BTreeMap oracle; custom table tests and doctest passed.
Times are nanoseconds per lookup, shown as median [minimum, maximum].
A winner must beat each competitor by >5% in all six matched blocks.
The variability range describes these samples, not a confidence interval.

## local

| Workload | Plain | Tagged | std | Winner |
|---|---:|---:|---:|---|
| small_hit50 | 5.15 [4.83, 5.69] | 4.86 [4.82, 4.90] | 1.59 [1.50, 2.14] | std |
| small_miss87 | 18.04 [17.01, 19.28] | 17.44 [16.89, 17.84] | 12.75 [12.36, 13.07] | std |
| large_hit50 | 6.00 [5.92, 6.14] | 5.26 [5.17, 5.33] | 2.10 [1.98, 2.40] | std |
| large_miss87 | 29.33 [28.55, 30.06] | 25.99 [25.12, 26.79] | 15.06 [14.74, 17.57] | std |
| large_deleted_miss | 99.80 [96.67, 102.42] | 96.81 [95.12, 107.88] | 14.02 [13.68, 14.62] | std |
| large_rebuilt_miss | 8.69 [8.32, 9.50] | 8.22 [8.18, 8.72] | 1.68 [1.61, 1.79] | std |

Environment: macOS-26.7.1-arm64-arm-64bit-Mach-O. CPU affinity: None.

CPU model query was denied by the local sandbox. The runner retained that error
in environment.json. No model identity is inferred from earlier runs.

## linux-arm

| Workload | Plain | Tagged | std | Winner |
|---|---:|---:|---:|---|
| small_hit50 | 7.78 [7.73, 7.86] | 8.39 [8.28, 8.64] | 3.87 [3.83, 3.92] | std |
| small_miss87 | 36.38 [36.26, 36.50] | 33.30 [33.18, 33.68] | 20.45 [20.17, 20.73] | std |
| large_hit50 | 12.30 [12.23, 12.38] | 10.89 [10.82, 10.97] | 9.20 [9.12, 9.46] | std |
| large_miss87 | 75.12 [74.89, 75.69] | 50.94 [50.27, 51.75] | 24.14 [24.08, 24.17] | std |
| large_deleted_miss | 152.49 [152.25, 152.94] | 137.14 [137.08, 137.70] | 23.19 [23.14, 23.22] | std |
| large_rebuilt_miss | 15.13 [15.06, 15.28] | 13.58 [13.54, 13.61] | 3.86 [3.82, 3.94] | std |

Environment: Linux-6.12.111-136.204.amzn2023.aarch64-aarch64-with-glibc2.34. CPU affinity: [0].

Full CPU identity, features and compiler build are in `linux-arm/environment.json`.

## linux-x86

| Workload | Plain | Tagged | std | Winner |
|---|---:|---:|---:|---|
| small_hit50 | 9.57 [8.17, 12.64] | 10.80 [7.92, 13.17] | 5.28 [3.33, 7.67] | std |
| small_miss87 | 32.98 [32.71, 33.14] | 30.51 [30.38, 30.72] | 15.33 [14.79, 15.57] | std |
| large_hit50 | 15.38 [14.90, 16.07] | 13.13 [13.04, 13.85] | 11.70 [10.86, 11.82] | std |
| large_miss87 | 57.47 [56.59, 57.91] | 43.22 [43.07, 43.67] | 19.12 [19.05, 19.26] | std |
| large_deleted_miss | 173.52 [172.30, 174.65] | 170.89 [170.33, 171.24] | 17.93 [17.85, 18.06] | std |
| large_rebuilt_miss | 14.55 [14.37, 14.82] | 14.18 [14.14, 14.26] | 4.02 [3.98, 4.05] | std |

Environment: Linux-6.12.113-138.209.amzn2023.x86_64-x86_64-with-glibc2.34. CPU affinity: [0].

Full CPU identity, features and compiler build are in `linux-x86/environment.json`.

## Workload-specific decisions

Rust HashMap wins every workload on each of the three machines under the
all-six-blocks rule. This supports the library baseline for these warm integer
lookups. It does not establish a winner for unmeasured mutation or key types.

Among the scalar implementations, Arm small-table hits favor plain probing:
7.78 ns median versus 8.39 ns tagged. Arm large-table misses favor filtering:
75.12 ns plain versus 50.94 ns tagged. On x86, plain/tagged comparisons for
both deleted and rebuilt misses are practical ties; small hits are unresolved.
The other three x86 cells favor tagged. Locally, large hits and large misses
favor tagged; the other four scalar comparisons remain unresolved. Pair ratios
and exact extrema are retained in summary.json.

## Probe work and interpretation

The scalar variants visit identical control positions for every matched workload.
Tag filtering changes full-key equality work. These counts are collected outside
the timer, after timing has completed. Values below are means per query from seed 1000.

| Workload | Probes/query | Plain equalities/query | Tagged equalities/query |
|---|---:|---:|---:|
| small_hit50 | 1.504 | 1.504 | 1.004 |
| small_miss87 | 21.159 | 20.159 | 0.158 |
| large_hit50 | 1.507 | 1.507 | 1.004 |
| large_miss87 | 33.514 | 32.514 | 0.253 |
| large_deleted_miss | 33.514 | 16.206 | 0.126 |
| large_rebuilt_miss | 2.080 | 1.080 | 0.009 |

Each scalar slot has 16 payload bytes plus one control byte: 68 KiB for 4096
slots, 4.25 MiB for 262144 slots, excluding headers/allocator overhead. The
standard capacity column reports usable capacity; it is not a physical-byte
measurement. Its erasure policy can alter reported usable capacity.

The deleted and rebuilt workloads retain the same 114688 live keys. Rebuilding
removes scalar tombstones and changes placement. Since rebuild time is excluded,
the result establishes a post-maintenance lookup effect, not a profitable
maintenance threshold. Growth, allocation, erase latency, cold-cache access,
string/large keys, adversarial keys, iteration and concurrency remain unmeasured.

The same mixer makes the standard-map comparison more controlled, but the
implementations still differ in probing, backend, layout and erase policy. A
speed difference cannot be assigned to SIMD without code-generation and hardware
evidence. No architecture-wide speed claim follows from two Linux hosts.

The initial Linux campaign used source 77a7994. It is excluded from all tables.
After an optional macOS sysctl query failed before collecting local samples,
the runner was changed to retain metadata failures and the entire final campaign
was repeated on all three machines at the exact source above. No timing samples
from the final campaign were discarded.

Raw rows, environment, full paired comparisons and host validation logs are
retained alongside this document. All setup and oracle work precedes lookup
timing. Clock, thermals, competing load and SMT siblings were uncontrolled.
