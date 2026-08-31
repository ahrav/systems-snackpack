# Measurement records

This directory holds compact records from exact-source correctness runs on the
required Arm and x86-64 Linux hosts. Topic 52 makes no timing or architecture
performance comparison.

Each checked-in host record must bind:

- the pushed source commit and path-limited archive SHA-256;
- target label, runtime-resolved hostname, architecture, kernel, processor,
  compiler, build flags, and binary digest;
- filesystem type, mount source and options, block size, and reflink capability;
- all four deterministic cut results, two complete A/A results, the checksum
  corruption control, reflink isolation control, and code-generation checks;
- a sealed external receipt archive, its SHA-256, its uncompressed manifest
  digest, and the independent controller validation result.

Full receipts remain outside Git. A compact comparison may report only exact
observations and derived model outputs. It must state that process exit leaves
the kernel alive, and it must carry the full experiment boundary: no power-loss,
filesystem-replay, torn-sector, controller-cache-loss, delayed input/output
error, timing, Btrfs, or OpenZFS claim.

The preliminary exploration is not publication evidence. Only a receipt built
from the final path-limited Git archive qualifies.

The accepted exact-source records are the [Arm host record](2026-08-31-arm.md),
the [`xxl` host record](2026-08-31-xxl.md), the [bounded
comparison](2026-08-31-comparison.md), and the [compact receipt
bundle](raw/2026-08-31-70c4821/README.md).
