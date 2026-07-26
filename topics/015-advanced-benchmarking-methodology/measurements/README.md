# Measurement contract

The focused experiment measures two calls to the same checksum in each fresh
process.

## Timed boundary

Included:

- one complete traversal of the 32 MiB target;
- two `Instant` reads around each checksum call.

Excluded:

- process startup;
- allocation and target initialization;
- the 256 MiB eviction-buffer traversal;
- CSV formatting and output.

Environment variables `BENCH_TARGET_MIB` and `BENCH_THRASH_MIB` can change the
working sets. Records include both byte counts.

## Replication and assignment

- Twelve temporal blocks.
- One fresh `AB` process and one fresh `BA` process per block.
- Alternating launch order between blocks.
- One order-cancelled label ratio per block.
- Median and type-7 interquartile range across the twelve block ratios.

The twelve blocks are the nominal analysis units. Treating their contrasts as
independent is an experimental assumption, not a property established by
fresh processes. The 48 timed calls are not 48 independent replicates.

## Acceptance checks

- Every process emits both labels and both positions.
- Every process returns matching checksums.
- Every process records the same target and eviction-buffer sizes.
- Every process places its labels in the order its `order` column declares.
- Every block contains one `AB` and one `BA` process, at launches 1 and 2, with
  the first launch alternating between blocks.
- Duplicate rows, duplicate block orders, and non-positive intervals are
  rejected rather than overwritten.
- The linked image contains the intended checksum symbol and call sites.
- The retained source manifest covers the topic tree and the workspace build
  inputs the measured binary inherits.
- The affinity branch that executed is recorded, not assumed.
- Raw records remain available beside each summary.

`order_bias.sha256` is a digest-only record. The measured binary is not
retained, so the digest cannot be re-verified with `sha256sum -c`. The
`95bd13b` snapshots retain curated code-generation excerpts —
`codegen-checksum.txt`, and `codegen-measure-pair.txt` on the x86-64 host — not
a full disassembly, so the linked image cannot be re-inspected beyond those
excerpts. Runs from this contract onward retain `codegen-full.txt.gz` and
`order_bias.symbols.txt` as well. Those snapshots also recorded the digest
against an absolute build path, which they preserve unchanged.

The result applies to the recorded source, linked image, host, toolchain,
flags, workload, affinity boundary, and run window. The affinity boundary is
the runner branch that executed; raw rows do not record the CPU each timed call
actually ran on.

## Retained records

- [AArch64 host record](2026-07-25-arm.md)
- [x86-64 host record](2026-07-25-xlg.md)
- [cross-host comparison](2026-07-25-cross-host.md)
- [raw process and code-generation evidence](raw/95bd13b/)
