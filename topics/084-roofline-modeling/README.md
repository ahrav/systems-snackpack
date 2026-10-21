# Roofline modeling and algorithmic performance ceilings

Compare three schedules for `y = (3*x + 1)*2`: full temporary (`split`),
1024-element scratch (`blocked`), and one fused pass (`fused`). The intermediate
has no external consumer, so all schedules satisfy the same output contract.
Separate stage functions deliberately retain the split and blocked boundaries.
All arrays use `f64`. Inputs `k/16`, for integer `-512 <= k <= 511`, keep every
operation exact. A separate integer formula and Python rational oracle verify
outputs. This input domain does not test arbitrary floating-point equivalence.

```sh
cargo +1.93.1 test -p roofline-modeling
cargo +1.93.1 run --release -p roofline-modeling -- fused 16777216 4
python3 topics/084-roofline-modeling/experiment/oracle.py target/release/roofline-modeling
python3 topics/084-roofline-modeling/experiment/run.py /tmp/topic084-fresh-results
```

The runner refuses an existing results directory. It builds source directly with
Rust 1.93.1, native target, opt3, one codegen unit, LTO off and panic unwind. Linux
runs pin to the first allowed CPU and verify the affinity mask. Source/binary
hashes, toolchain, cache sizes, host identity, assembly and all command attempts
are retained. It writes `samples.csv` only after all processes succeed.

Each size (1024, 262144, 16777216 elements) has six fresh processes per candidate,
one for each permutation of candidate order. Each process warms three passes,
then processes 2^26 elements in total. Timed code includes stage calls and scratch
accesses. Allocation, first touch and full output checking are outside timing.
`black_box` keeps each pass observable. Split allocates N scratch values, blocked
1024, and fused none. This is a warm steady-state kernel contract.

## Model and byte contract

For operation count F, transferred bytes Q, bandwidth B and compute ceiling C:

```text
T >= max(F/C, Q/B)
I = F/Q
F/T <= min(C, B*I)
ridge intensity = C/B
```

Use matching precision, operation convention, core count, memory boundary and
load/store mix. Here algorithmic work is 3N FLOPs. Output GFLOP/s uses that count;
it is not a measurement of retired floating-point operations.

Source-level traffic is 32N bytes for split and blocked, and 16N for fused.
Conditional DRAM traffic is 48N for split and about 24N for fused/blocked.
Those estimates assume streaming full cache lines, cold write-allocate output
stores with eventual writeback, an evicted full temporary, and resident blocked
scratch. Actual stores, reuse, prefetch and writeback timing can change them.
No measured DRAM byte count or calibrated hardware roof is claimed.

Calibrate bandwidth independently. Using this kernel's Q/T as B makes B*I equal
F/T by construction. A point then lies on its own line without showing saturation.
Hierarchical analysis needs separate Q and B for each cache/memory boundary.

Choose by elapsed time for equivalent output. Changing algorithms can reduce
both time and GFLOP/s. Bound fractions of application time separately.

## Comparison rule

For each workload and host, report median and min/max ns/item. Compare candidates
within each of six order blocks. A wins if all six B/A time ratios exceed 1.05.
B wins if all six ratios are below 1/1.05. A practical tie requires every ratio in
[1/1.05, 1.05]; otherwise the result is unresolved. This descriptive fixed-sample
rule provides no population confidence interval. Shared-host load, clock policy,
allocator placement and page policy are not controlled. Timing alone cannot
attribute a result to a cache level or architecture.

## Sources

- [Williams, Waterman, Patterson: original Roofline report](https://www2.eecs.berkeley.edu/Pubs/TechRpts/2008/Archive/EECS-2008-134.pdf): DRAM boundary and bound.
- [Intel memory-level Roofline](https://www.intel.com/content/www/us/en/developer/articles/technical/memory-level-roofline-model-with-advisor.html): separate cache boundaries.
- [STREAM methodology](https://www.cs.virginia.edu/stream/ref.html): bandwidth workloads and cache sizing.
- [Wang et al., Time-Based Roofline](https://arxiv.org/html/2009.04598): time and algorithm work must be considered together.

[Measured results and limits](measurements/RESULTS.md).
