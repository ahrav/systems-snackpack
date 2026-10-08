# Final exact-source measurements

Source `d6be170cfe0f60718374b387e0295c20556ec90f`. Both required Linux hosts pass four unit tests, one doctest, Clippy and 234 process runs. All source hashes, final-value oracles, mapping/reserve checks and finite-window identities pass.

[All cells](results.md), [medians/IQRs and paired ratios](summary.json), [source/platform receipt](receipt.json). Raw evidence: `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-071/2026-10-08-64dd765c/final-fixed`.

Greedy wins modeled programmed-page work in eight random/hot cells per host. RR and greedy exactly tie in four cyclic cells; all three tie in the 32-write initial-space cell. RR wins elapsed time in 9 Arm and 4 x86 cells; 13 host/cells remain unresolved.

Elapsed rule: rival/candidate elapsed time >=1.05 for every rival in all six pairs, meaning 1.05x replay speed or at least 4.76% less elapsed time. Program-work rule: candidate/rival programmed pages <=0.99 in all six paired traces. These descriptive thresholds are not confidence bounds.

The first committed campaign is retained separately. A final-range whitespace check found a trailing manifest blank line; its removal changed the frozen manifest hash and justified this exact-source replay. Both measured binaries are byte-identical to the prior campaign. No timings are pooled or selected across campaigns.

Fixed warmup is not verified equilibrium. No physical device I/O, wear, p99, energy, cold-cache or architecture-only inference. Compiler/toolchain differences and shared-CPU variation remain.

Representative 64-block/90%-occupied uniform elapsed medians and IQR:

- arm: rr 43.70 ns/write (IQR 43.45–44.08), greedy 65.49 ns/write (IQR 65.32–65.60), sample4 48.03 ns/write (IQR 47.94–48.11).
- x86: rr 39.61 ns/write (IQR 39.33–41.02), greedy 62.91 ns/write (IQR 62.50–63.27), sample4 44.82 ns/write (IQR 43.96–45.73).
