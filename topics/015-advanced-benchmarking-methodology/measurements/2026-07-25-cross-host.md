# 2026-07-25 cross-host record

Both hosts ran source commit
`95bd13b16011d38ee325e49eeef196d03db6611e` from archive SHA-256
`ea398c0ef816f0c43d40162ee6f2c827232791817c3c9a1b083a21c03c85eece`.
Their source manifests are identical and match the archived `95bd13b`
candidate. Both extracted trees passed the required Cargo gates, the focused
correctness checks, the process schedule checks, and linked-code inspection.
Later files in this directory are retained evidence, not changes to the
executed code.

Each host used 12 temporal blocks, 24 fresh processes, and 48 timed calls. The
runner was configured to use `taskset -c 0`; later probes found `taskset` on
both hosts, but raw rows do not directly record actual affinity. One block,
not one inner call, is the nominal analysis unit for the label contrast.
Independence between block contrasts is an experimental assumption; neither
run tested temporal autocorrelation. Each IQR is descriptive dispersion
across 12 block ratios in one run window, not a confidence interval.

## Label-ratio results

| Schedule | AArch64 2b median [IQR] | x86-64 xlg median [IQR] |
| --- | ---: | ---: |
| fixed `AB`: A / B | 0.993444 [0.989788–0.999396]x | 1.333422 [1.314173–1.356530]x |
| fixed `BA`: A / B | 1.009642 [1.005644–1.015109]x | 0.744930 [0.740145–0.747487]x |
| order-cancelled A / B | 1.000955 [0.995425–1.008619]x | 0.997165 [0.982715–1.007531]x |

Fixed order names opposite winners on each host. The distortion was modest in
the AArch64 run and large in the x86-64 run. Balanced assignment and one
geometric contrast per block returned both A/A controls close to their known
identity.

For the known A/A truth, each fixed schedule put the same label on opposite
sides of unity. Either fixed schedule would therefore misattribute position to
the label in these run windows. The result does not prove that all order
effects are multiplicative, that balancing removes every bias, or that 12
blocks are enough for a production decision.

## Code generation and mechanism boundary

The AArch64 native binary used an SVE checksum loop. The x86-64 native binary
used an AVX-512 checksum loop with AVX2 and scalar remainder paths. These are
linked-image observations. The two binaries, CPU products, compiler versions,
and host states differ.

The x86-64 second position was much faster than its first position. The
AArch64 position difference was smaller and reversed. The experiment did not
measure PMU events, cache occupancy, frequency residency, interrupts, or
concurrent host load. A cache-state explanation for the x86-64 result is
plausible but remains inferred. No absolute time or position-effect difference
should be generalized to an ISA, vendor, or CPU family.

Read the [AArch64 record](2026-07-25-dev-dsk-ahrav-2b.md), the
[xlg record](2026-07-25-xlg.md), and the
[retained raw evidence](raw/95bd13b/).
