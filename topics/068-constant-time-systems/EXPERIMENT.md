# Frozen experiment

Contract: byte equality with public lengths/addresses and a declassified final
Boolean. Zero length compares equal; unequal lengths compare false. Every
candidate is checked against Rust slice equality before performance selection.
Exhaustive single-byte pairs, empty/unequal lengths, every mismatch position,
unaligned subslices and deterministic multi-mismatch cases cover edge behavior.

Candidates: early exit (security-rejected control), XOR/OR reduction (uncertified
teaching code), subtle 2.6.1 ConstantTimeEq (best-effort library protection).
Build: release, native target, LTO off, dependency default features disabled.

Lengths 16,32,256,4096; first mismatch, last mismatch, equal. Each cell uses
12 paired blocks, rotating three candidate orders then their reversals, twice.
There are 432 fresh processes per host. Each process doubles repetitions until
a batch takes at least 5 ms, then measures one batch. The independent sample is
the process, never an inner iteration. Warmup and correctness precede timing.

Timer includes calls, benchmark black_box and checksum accumulation. Input
allocation, generation, oracle, startup, printing and teardown are excluded.
Buffers are reused and resident. No cold-cache, random-arrival or network claim.
Shared-host load and CPU frequency are uncontrolled; Linux processes pin to the
first available CPU. Ranges show dispersion. Concurrent task-owned host work
must finish before the campaign.

Select the lowest median full-scan candidate only when every paired competitor /
winner ratio has its second-smallest value above 1.02. Report the second and
11th ordered ratios of 12 pairs: nominal 99.365% marginal sign interval under iid
continuous pairs, with no simultaneous coverage claim over multiple cells.
The early-exit timing winner is reported separately from security eligibility.
No candidate is security-certified by these measurements.

This is not dudect. Comparing repeated fixed-input throughput can illustrate
obvious path differences, but does not certify secret independence. A real
leakage campaign needs randomized, controlled classes, positive controls,
adequate power and exact target coverage. Failure to detect leakage is not proof.
