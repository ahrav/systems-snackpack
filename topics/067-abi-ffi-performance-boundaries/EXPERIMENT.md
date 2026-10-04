# Frozen experiment, 2026-10-04

Five correct alternatives: same-language Rust, per-item C, C batches of 256,
full borrowed C batch, and allocate/copy/full C batch/free per request. All compute
the same wrapping-u64 transform and reduction; independent u128 oracle runs first.
Lengths 1,31,4096,1048576; rounds 0 and16. Unit checks add empty/null-zero,
255/256/257 tails, overflow values, immutability and partition equivalence.
Native separate C compilation, static archive, -O3, no LTO; Rust release,
-C target-cpu=native -C lto=off. C -mcpu=native on Arm or -march=native on x86.
Each native run pins to the first CPU in the allowed affinity mask. No concurrent
build/measurement campaign on that host. Build/setup/checks occur before timings.
One fresh process per workload/candidate,10 paired order-balanced blocks: five
cyclic orders followed by their reverses. All candidates correctness-checked per
process. Doubling calibration until >=10ms precedes the fixed timed loop.
Result consumption/checksum is in the loop; process startup, input creation,
oracle and calibration are excluded. Copy allocation/copy/free is included.
Input generation time and full process elapsed are separate descriptive fields;
first-after-check is warm and must not be presented as first-touch or cold-cache.
This is a reused-input steady-state study; no cold-cache, managed runtime,
dynamic linking, asynchronous queueing or arrival-delay claim.
Criterion: lowest median ns/request is the point estimate. Name a resolved winner
only if all paired competitor/winner ratios have lower interval endpoint >1.02.
Intervals use2nd and9th sorted ratios of10 process pairs (97.85% marginal coverage
under independent continuous pairs); not simultaneous/multiplicity-adjusted.
Record full range dispersion. Preserve unresolved results. No reruns for a winner.
Batching can alter compiler visibility and loop optimization. Timings do not
isolate an ABI-only fixed call cost. Inspect final linked call sites and C bodies.
