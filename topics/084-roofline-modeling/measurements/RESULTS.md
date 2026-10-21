# Results: 2026-10-21

Fused beats split in all six host/workload cells. Fused wins against blocked in all Arm cells and the small x86 cell. The middle x86 cell is a practical tie; the large x86 comparison is unresolved. Split and blocked tie at 1024 elements on both hosts. Blocked beats split at both larger sizes.

| Host | Elements | Split ns/item | Blocked ns/item | Fused ns/item |
|---|---:|---:|---:|---:|
| arm | 1,024 | 0.2538 [0.2537, 0.2583] | 0.2546 [0.2542, 0.2566] | 0.1957 [0.1946, 0.1971] |
| arm | 262,144 | 0.4994 [0.4883, 0.5095] | 0.3244 [0.3226, 0.3365] | 0.2259 [0.2245, 0.2410] |
| arm | 16,777,216 | 0.6211 [0.6191, 0.6342] | 0.4931 [0.4872, 0.5056] | 0.3172 [0.3147, 0.3200] |
| xxl | 1,024 | 0.2131 [0.2118, 0.2160] | 0.2197 [0.2174, 0.2211] | 0.1489 [0.1487, 0.1498] |
| xxl | 262,144 | 1.1723 [1.1673, 1.1762] | 0.6173 [0.6132, 0.6216] | 0.5980 [0.5954, 0.5991] |
| xxl | 16,777,216 | 2.9705 [2.9194, 3.0497] | 1.6344 [1.6226, 1.6802] | 1.5487 [1.5314, 1.5830] |

Values are median [min, max] over six fresh processes. Each process has three warmup passes followed by 2^26 timed element transformations. The six orders cover all candidate permutations. The README defines the 5% descriptive selection rule. Complete pairwise ratios are in `raw/summary.json`.

## Identity and limits

Measured source commit: `3f6ea80d3af91ebe327e8c8a4c6dd00f89c40d37`. Final source and runner bytes match this commit. Source and archive SHA-256 are in `raw/source-identity.json`. Reproduce selection with `python3 experiment/analyze.py measurements/raw` from this topic directory.

Both hosts used Rust 1.93.1, LLVM 21.1.8, native target, opt3, one codegen unit, LTO off, panic unwind, one thread pinned to CPU0. All four unit tests and 15,393 Python rational-oracle values pass on each. Every timed process verifies every output after timing.

- Arm: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, AArch64, Arm Neoverse V1 (implementer 0x41, part 0xd40, variant r1p1, MIDR_EL1 `0x411fd401`; `lscpu` reports vendor ARM, model 1), 64 visible cores, one thread per core, Linux 6.12.111, glibc 2.34. CPU0 has 64 KiB L1d, 1 MiB L2 and 32 MiB LLC.
- xxl: SSH resolves to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, verified x86_64, Xeon Platinum 8488C, KVM, Linux 6.12.111, glibc 2.34. CPU0 has 48 KiB L1d, 2 MiB L2 and 105 MiB LLC.

Each large array is 128 MiB. The active split footprint is 384 MiB; fused uses 256 MiB; blocked uses 256 MiB plus 8 KiB scratch. Initialization and checks are excluded, so these results select warm kernel execution only. They do not measure allocation or application-wide latency.

Linked objdump excerpts show SVE vector multiply/add on Arm and YMM vector multiply/add on x86. Both preserve first/second stage calls; fused has one transform pass. Multiplication by two becomes addition to itself. These observations confirm the candidate shapes. They do not identify a unique cause for host differences.

DRAM bytes, PMU events, saturation and sustainable hardware ceilings were not measured. The Roofline figure uses illustrative inputs. Clock policy, SMT-neighbor activity, page policy, shared-host load and address placement are uncontrolled. No architecture-wide or population claim follows from these two machines.

Full process attempts, linked binaries, assembly, host observations and validation logs are retained in the automation evidence directory. Repository raw CSV and correctness records are sufficient to reproduce reported selections.
