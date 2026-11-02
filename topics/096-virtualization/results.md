# Topic 096 results

Measured implementation and runner: `8b88a8e7ae05f3a61373191bf36ba1dd02f04e9b`. Review follow-ups after that commit changed two files. `run.py` now rejects a recorded row whose checksum differs from the arithmetic sum the traversal must produce; all 48 recorded rows satisfy that check. The `malformed_geometry_faults` test now also asserts `Fault::Host` for a malformed host table behind a valid guest table. `probe.c` is unchanged, so the recorded source and binary hashes still identify the measured probe.

All three hosts passed 323,840 independent byte-oracle comparisons, three unit tests, and one doctest (local doctest in the workspace suite). The cold-walk test enumerates all 36 depth pairs from zero through five. Both Linux C probes verified every cycle link and arithmetic checksum in every process.

Linux: GCC 11.5.0, `-O2 -std=c11 -Wall -Wextra -Werror`; Rust 1.93.1. Kernel 6.12.113-138.209.amzn2023 on both architectures. Arm CPU implementer 0x41, part 0xd40, variant 0x1, revision 1; `evidence/arm-cpuinfo.txt` is a 30-line excerpt of /proc/cpuinfo that ends inside the processor 3 stanza, and the lscpu record in `evidence/arm-environment.txt` covers all 64 CPUs of the single socket. x86 CPU: Intel Xeon Platinum 8488C, KVM guest. Both use 4096-byte base pages and report 2097152-byte PMD geometry. The THP `enabled` and `defrag` settings are both `madvise` on both hosts. Local correctness: macOS arm64, Rust 1.93.1.

Per Linux host: 24 measured fresh processes and four excluded warmup processes. Six alternating AB/BA pairs per footprint, single-threaded, CPU 0 pinned before allocation. Timing and classification rules are in README.md. Host load, SMT-neighbor activity, clocks, thermals, and underlying host placement were uncontrolled. Default NUMA policy; no explicit memory binding.

Values are median [minimum, maximum]. Lower is better. The minor-fault column counts every fault between the two `getrusage` calls. The arena contributes exactly one fault per base page or per huge page; the remaining 1 to 2 faults come from the first `clock_gettime` call, which maps the vDSO data pages inside the window. On the Arm hardware, a variant that calls `now()` once before the first `getrusage` reports exactly 512 and 1 faults at 2 MiB in 10 of 10 runs each, with first-touch medians unchanged within run-to-run spread.

| Host | MiB | Policy | ns/load | First touch ms | AnonHugePages KiB | Minor faults |
|---|---:|---|---:|---:|---:|---|
| arm | 2 | base | 7.142 [7.071, 7.326] | 0.468 [0.454, 0.528] | 0 | 513–514 |
| arm | 2 | huge | 5.125 [5.107, 5.144] | 0.051 [0.048, 0.061] | 2048 | 2–3 |
| arm | 64 | base | 37.160 [34.550, 43.551] | 17.832 [17.533, 19.360] | 0 | 16385–16386 |
| arm | 64 | huge | 26.714 [26.582, 26.791] | 1.475 [1.447, 1.552] | 65536 | 33–34 |
| x86 | 2 | base | 5.202 [5.202, 5.203] | 0.560 [0.500, 0.706] | 0 | 513–513 |
| x86 | 2 | huge | 3.001 [2.952, 3.423] | 0.217 [0.119, 0.294] | 2048 | 2–2 |
| x86 | 64 | base | 19.115 [18.881, 19.160] | 22.786 [22.109, 23.179] | 0 | 16385–16385 |
| x86 | 64 | huge | 38.903 [38.864, 38.965] | 8.564 [8.320, 9.193] | 65536 | 33–33 |

Guest-side huge-page advice wins first touch for both footprints on both hosts. It wins steady traversal on Arm at 2/64 MiB and x86 at 2 MiB. Base pages win steady traversal on x86 at 64 MiB: median 19.115 versus 38.903 ns/load. Every named winner exceeds the declared 5 percent difference in all six pairs. There are no ties or unresolved cells under this descriptive rule.

Every huge-advice process reports full AnonHugePages coverage before and after traversal; base-policy processes report zero. These observations establish guest-visible backing for this mapping, subject to the smaps limitations in README.md. They do not reveal host-stage mapping sizes. Timing differences alone cannot identify translation, physical cache indexing, placement, or frequency as the cause.

One separate x86 perf diagnostic of huge/64 reproduced 38.898 ns/load. Its whole-process user-event counts were 265,102,117 cycles, 25,162,857 instructions, and 21,507 generic cache misses. It is excluded from campaign statistics and has no paired counter baseline. Generic cache misses cannot localize the cache level or prove a translation cause. Exact disassemblies are retained externally; the timed loop retains a dependent load and checksum.

Both hosts lack /dev/kvm, confirmed by one bounded recheck. Matched bare-metal/VM performance, controlled second-stage page-size treatments, VM exits, migration overhead, and host scheduler attribution remain unmeasured. macOS ran correctness only; the Linux mapping probe requires Linux APIs. A controlled KVM host with host-level mapping and PMU access is required for the remaining virtualization attribution experiment.

All six repository validation commands passed. Initial local test compilation needed explicit usize inference; Clippy then required is_multiple_of. Both were corrected before the measured commit. The first evaluator fetch was denied by its checkout permissions; a read-only GitHub API request supplied the current lock. An unquoted API query and a wrong source-owner path were corrected before the status result. These preparation failures are separate from measurement.
