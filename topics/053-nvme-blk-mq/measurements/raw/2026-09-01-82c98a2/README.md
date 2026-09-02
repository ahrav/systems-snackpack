# Exact-source receipt bundle

This directory publishes compact evidence for the accepted Topic 53
experiments from source commit
`82c98a25eb4ad31fd9e18fc8d8f9463dab6854d7`.

- `source.txt` binds the source commit, topic path, archive prefix, and source
  archive SHA-256.
- `arm-results.external.txt` and `xxl-results.external.txt` locate the retained
  sealed receipt archives and bind their archive and uncompressed-manifest
  digests.
- `arm-controller-validation.json` and `xxl-controller-validation.json` are
  the exact independent controller-validation outputs for the retrieved
  receipts.
- `xxl-resolution.txt` is the exact controller-side record of the `xxl` alias,
  configured hostname, answering runtime hostname, architecture, and
  observation time.
- `SHA256SUMS` binds every checked-in file in this directory except itself.

The compact records derived from these receipts are the [Arm host
report](../../2026-09-01-arm.md), [`xxl` host
report](../../2026-09-01-xxl.md), and [cross-host
comparison](../../2026-09-01-comparison.md).

Each external receipt has a 365-entry content manifest. It retains exact
source and launcher identity, source hashes before and after execution, host
and block-path snapshots, native build evidence, compiler assembly and focused
disassembly, two fixed 32-process campaigns, per-process counter windows,
analysis, controls, cleanup, a content manifest, and a read-only seal.

Each timed process performed 8,192 verified 4 KiB `O_DIRECT` reads, or
33,554,432 bytes. One complete four-process block was the analysis unit. The
full receipts stay outside Git because their detailed snapshots, binary,
assembly, and per-process files are too large and noisy for review.

Only the two accepted sealed receipts listed here contribute the reported
timings.

The result covers each exact host's live XFS file path through the guest block
stack. Application depth does not establish blk-mq or NVMe queue occupancy.
Linux AIO completions are not NVMe completion-queue entries. Device counters
may contain ambient traffic. An Amazon EBS device exposed through guest NVMe
does not prove local flash. Cross-host differences do not establish an
instruction-set, CPU-vendor, storage-vendor, filesystem-wide, or general NVMe
effect.
