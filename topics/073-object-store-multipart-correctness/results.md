# Topic 073 final results

Measured source: `e91e7352dc12e2da20bcc407418c29c757cbb4a8`.
Apple M1 Pro, Darwin 25.6.0, 10 available logical CPUs, Rust 1.93.1 / LLVM 21.1.8.
Fresh verbose build confirmed `-C opt-level=3`, no explicit target CPU/features.
Bare rustc cfg is informational; effective settings come from the compiler invocation.
Local CPU affinity was not controlled. Six paired process blocks per cell, 108 processes total.

Each cell shows median [observed min, max], in microseconds per complete normalization.

| Parts-order-copies | Sort us | Tree us | Slots us | Selection |
|---|---:|---:|---:|---|
| 8-ordered-1 | 0.050 [0.048, 0.052] | 0.154 [0.152, 0.167] | 0.041 [0.040, 0.044] | slots |
| 8-shuffle-4 | 0.203 [0.199, 0.264] | 0.275 [0.269, 0.299] | 0.076 [0.075, 0.081] | slots |
| 1024-reverse-1 | 2.084 [2.065, 2.257] | 32.240 [28.025, 44.126] | 1.499 [1.482, 1.985] | slots |
| 1024-shuffle-4 | 39.928 [39.575, 40.707] | 189.073 [184.819, 203.626] | 5.029 [4.657, 5.447] | slots |
| 10000-ordered-1 | 19.131 [18.432, 22.327] | 569.218 [546.789, 628.457] | 16.104 [15.580, 18.930] | unresolved |
| 10000-shuffle-4 | 613.145 [586.540, 967.933] | 2700.286 [2646.450, 5026.086] | 99.205 [94.172, 104.396] | slots |

Slots won five local cells by the predeclared all-six-pairs 5% rule. The
10000-part ordered cell is unresolved despite a lower slots median. The initial
campaign had an unresolved small ordered cell; subsequent runs were required by
runner provenance corrections, not selected to obtain a winner. Earlier observations
remain retained and are not pooled. Treat close cases as sensitive to run conditions.
No further winner-seeking rerun was performed.

Allocation, validation, normalization, output and teardown are timed. Oracle, input
generation, startup, compilation, networking and durable journals are excluded.
These results select local bookkeeping, not S3 upload concurrency or throughput.
Numeric receipt tokens are fixtures; ETag string allocation and serialization are
not represented. No cold-cache, p99, A/A calibration, PMU or ISA-wide claim.

Both required Linux hosts failed authentication before host identity verification
and transfer. Their exact-source campaigns remain pending; no Linux winner exists.

The runner binds the executable to Cargo JSON from a new verbose build target.
Four unit tests, one doctest, Clippy, and all seven workspace gates passed.
A fresh review reproduced two runner provenance defects and verified their repairs.
Final 108 rows, summaries, exact source hashes and byte-identical binary independently
recomputed. See EVIDENCE_RECEIPT.json for source, binary, host, results and raw paths.
