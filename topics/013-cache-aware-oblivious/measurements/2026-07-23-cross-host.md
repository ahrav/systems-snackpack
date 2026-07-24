# 2026-07-23 cross-host record

Both hosts ran the same source archive: SHA-256
`51a39afc9da86c2a7c070e69b0b714cdb56dd1819cfae6e882bc7730c4721292`,
with embedded commit
`053e8f4d269e93276020a7937587762303e0104b`. Both runners passed the full
workspace gates, correctness example, binary reverification, source
reverification, and strict schedule checks. After relocation into this
repository, each 26-file evidence manifest passed `sha256sum -c`.

Each mode has 12 CPU-0-pinned fresh-process replicates in 12 order-balanced
six-mode blocks. The table reports focused kernel medians and descriptive
process interquartile ranges. It does not treat matrix elements or loop
iterations as independent samples. Each interval contains one dispatch and one
post-conditioning transpose. It excludes startup, but it is not a repeated
steady-state measurement.

| Mode | AArch64 2b median [IQR] | x86-64 xlg median [IQR] |
| --- | ---: | ---: |
| `pow2-naive` | 19.963515 [19.790534–19.989266] ms | 30.736585 [30.695686–30.804229] ms |
| `pow2-tiled` | 8.763907 [8.754564–8.782560] ms | 14.103765 [14.081759–14.128726] ms |
| `pow2-recursive` | 9.836988 [9.784642–9.859580] ms | 14.744519 [14.714341–14.815075] ms |
| `padded-naive` | 7.217866 [7.190889–7.267161] ms | 10.034099 [10.014559–10.075536] ms |
| `padded-tiled` | 6.654559 [6.579842–6.679490] ms | 10.020599 [10.004584–10.092629] ms |
| `padded-recursive` | 6.185996 [6.166957–6.221654] ms | 9.810758 [9.777290–9.924043] ms |

The order-balanced paired ratios expose the result more directly:

| Paired kernel ratio | AArch64 median [IQR] | x86-64 median [IQR] |
| --- | ---: | ---: |
| power-of-two naive / tiled | 2.278091 [2.256209–2.285341]x | 2.180148 [2.174778–2.184384]x |
| power-of-two naive / recursive | 2.021363 [2.009180–2.035847]x | 2.083465 [2.071988–2.094972]x |
| padded naive / tiled | 1.084643 [1.078231–1.095054]x | 1.000888 [0.995886–1.003695]x |
| padded naive / recursive | 1.167675 [1.157004–1.171593]x | 1.018844 [1.014116–1.028469]x |
| naive power-of-two / padded | 2.759214 [2.741062–2.772253]x | 3.061985 [3.052751–3.075028]x |
| tiled power-of-two / padded | 1.317856 [1.313405–1.327344]x | 1.407050 [1.392515–1.413735]x |
| recursive power-of-two / padded | 1.586054 [1.581461–1.596548]x | 1.503522 [1.485678–1.516433]x |

## Observed, derived, and inferred

Measured elapsed time shows the same qualitative result on these two hosts:
the power-of-two naive traversal was slower than either locality-preserving
kernel, and changing only `ld` from 2,048 to 2,049 sharply reduced every
power-of-two mode's time. On xlg, the padded naive/tiled paired-ratio IQR crosses
`1.0x`; on the AArch64 host, the padded tiled and recursive variants retained
larger advantages.

The simple modulo model gives a concrete hypothesis. A 2,048-element `u64`
leading dimension advances by 16,384 bytes, or 256 cache lines. In the reported
simple geometry, that stride repeats one L1 set candidate on both hosts,
8 of 2,048 L2 set candidates, and 128 of 32,768 L3 set candidates. The
2,049-element stride is not an integer number of lines and changes the page and
line offsets over the traversal.

Those calculations are derived from virtual layout and reported cache geometry.
They are not observations of cache-set occupancy. The AArch64 L1 reports more
set-index bits than fit in a 4 KiB page offset. The xlg L2 and L3, and the
AArch64 L1 through L3, likewise require physical-address information or
implementation knowledge beyond the shared page offset. Shared-cache hashing
or slicing may also differ from simple modulo indexing. All recorded bases had
the same 16-byte page offset, and the allocator produced a fixed relative
source-destination distance for each leading dimension rather than randomized
relative placement.

The measured timing, layout perturbation, and scalar linked code are consistent
with harmful set reuse in the power-of-two traversal. They do not prove that
conflict misses caused the difference. Prefetch, TLB, bank, replacement,
write-allocation, and physical-placement effects were not independently
classified. Both pagemap probes returned zero PFNs, and neither benchmark
observed the NUMA placement of its Rust allocations. CPU-0 pinning and first
touch do not replace that observation. The runs did not record PMU events,
frequency residency, CPU isolation, or concurrent host load.

Absolute host timing is not an ISA or vendor comparison. The CPU models,
virtualization, cache geometry, CPU count, NUMA policy, generated instructions,
and host state differ. Read the
[AArch64 record](2026-07-23-dev-dsk-ahrav-2b.md), the
[xlg record](2026-07-23-xlg.md), and the retained
[raw evidence](raw/053e8f4/).
