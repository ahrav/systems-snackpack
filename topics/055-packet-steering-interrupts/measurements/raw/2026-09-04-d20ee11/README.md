# Exact-source receipt bundle

This directory publishes compact evidence for the accepted Topic 55 campaign
from source commit `d20ee11bbb3c2cef2e98a69194d287783c5e29d6`.

- `source.txt` binds the source, archive, runner, and probe identities.
- `arm-controller-validation.json` and `xxl-controller-validation.json` are
  the exact independent validator results.
- `arm-results.external.txt` and `xxl-results.external.txt` locate the retained
  read-only receipts and their archives.
- `xxl-resolution.txt` binds the SSH alias to its runtime hostname and
  architecture.
- `SHA256SUMS` binds every checked-in file here except itself.

Each host receipt contains 149 files. It retains the exact source archive,
native binary, build checks, host and route inventory, steering and IRQ state,
24 client outputs, 24 server outputs, before and after snapshots, content
manifest, and read-only seal. The complete receipts stay outside Git because
the per-flow output, binaries, and host snapshots are too noisy for review.

The campaign is a correctness and placement observation. It makes no timing
claim. Positive NAPI identifiers do not reveal RSS keys, hash fields, or
indirection entries. Zero software-steering maps describe only these hosts and
this run. The shared server socket does not expose per-flow CPU placement.

The compact reports are the [Arm record](../../2026-09-04-arm.md), [`xxl`
record](../../2026-09-04-xxl.md), and [comparison](../../2026-09-04-comparison.md).
