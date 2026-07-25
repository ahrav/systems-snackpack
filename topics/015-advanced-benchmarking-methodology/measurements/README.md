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
- Every block contains one `AB` and one `BA` process.
- The linked image contains the intended checksum symbol and call sites.
- Raw records remain available beside each summary.

The result applies to the recorded source, linked image, host, toolchain,
flags, workload, affinity, and run window.

## Retained records

- [AArch64 host record](2026-07-25-dev-dsk-ahrav-2b.md)
- [x86-64 host record](2026-07-25-xlg.md)
- [cross-host comparison](2026-07-25-cross-host.md)
- [raw process and code-generation evidence](raw/95bd13b/)
