# Final exact-source measurements

Source `64dd765c496a355ff2f518925666e637189d7b65`. Both required Linux hosts pass four unit tests, one doctest, Clippy and 234 process runs. All source hashes, final-value oracles, mapping/reserve checks and finite-window identities pass. Matched model counters are identical across hosts.

[All cells](results.md), [medians/IQRs and paired ratios](summary.json), [source/platform receipt](receipt.json). Raw logs and replay archives are retained at `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-071/2026-10-08-64dd765c`.

Greedy wins model programmed-page work in eight random/hot cells per host; RR+greedy counts tie in four cyclic cells; all three tie in the 32-write startup cell. RR wins elapsed time in nine Arm and three x86 cells; fourteen host/cells unresolved under the predeclared speed rule: rival/candidate elapsed time >=1.05 for every rival in all six pairs. This is at least 4.76% less elapsed time. WAF selection requires candidate/rival programmed pages <=0.99 in all six paired traces. These descriptive thresholds are not confidence bounds.

Fixed warmup is not verified equilibrium. No physical device I/O, wear, p99, energy, cold-cache or architecture-only inference. Compiler/toolchain differences and shared-CPU variation remain. Initial pilot results are retained separately and never pooled. An initial output-format compile error was repaired before the successful pilot; the final runner differs by corrected elapsed-time wording, contract hashing and standalone lint settings.

Representative 64-block/90%-occupied uniform elapsed medians and IQR:

- arm: rr 43.86 ns/write (IQR 43.43–44.65), greedy 65.64 ns/write (IQR 65.28–65.84), sample4 48.03 ns/write (IQR 47.76–48.14).
- x86: rr 39.25 ns/write (IQR 38.40–44.31), greedy 61.93 ns/write (IQR 61.68–62.20), sample4 44.16 ns/write (IQR 43.34–45.98).
