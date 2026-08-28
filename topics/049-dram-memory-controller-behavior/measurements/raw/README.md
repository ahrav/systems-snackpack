# Raw receipt contract

Each accepted host bundle contains the immutable receipt created from one
path-limited source archive: source and binary identities, host and topology
metadata, every chronological attempt, the fixed schedule, linked disassembly,
the analyzer result, the independent validator result, and the inner seal.

The standalone validator receives expected source commit, archive digest,
target label, hostname, and architecture from the controller. It recomputes the
schedule, treatment signs, formulas, and result invariants without importing
the acquisition runner or analyzer.

[`2026-08-28-8ad9502/`](2026-08-28-8ad9502/) contains both accepted receipts,
their controller-side validations, and the entire rejected first Arm campaign.
The rejected receipt is retained for audit but contributes no estimate.
