# Exact-source receipt bundle

This directory publishes compact evidence for the accepted Topic 52
correctness runs from source commit
`70c4821cb0241b3acd620b2d2126521728739c15`.

- `source.txt` binds the source commit, archive prefix, and archive SHA-256.
- `xxl-resolution.txt` records the runtime alias resolution and kernel identity.
- `arm-results.external.txt` and `xxl-results.external.txt` bind the retained
  sealed receipt archives and their uncompressed manifest digests.
- The controller-validation JSON files record independent revalidation of each
  retrieved receipt.
- `SHA256SUMS` binds every checked-in file in this directory except itself.

Each sealed receipt contains 50 manifest-covered files. Both include exact
source and host identity, source hashes before and after execution, native
build output, assembly, disassembly, four deterministic cuts, two complete A/A
runs, a corruption control, a reflink isolation control, the receipt content
manifest, and a read-only seal.

These receipts predate the launcher binding, so they carry no `runner_sha256`
and the current validator rejects them on that check. Their controller-validation
JSON records the result of the validator contemporary with the run, and their
launcher provenance rests on the controller procedure rather than on a receipt
record.

The runs test process exits on XFS while the kernel remains live. They make no
power-loss, filesystem-replay, torn-sector, controller-cache-loss, delayed
input/output error, timing, instruction-set performance, Btrfs, or OpenZFS
claim. That exclusion list matches the experiment boundary in
`topics/052-filesystem-crash-semantics/experiment/README.md`.
