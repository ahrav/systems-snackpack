# Tail-latency histogram merge errors

A service has many workers, but its users experience one combined latency
distribution. A percentile is an order statistic: under the nearest-rank
definition used here, p99 selects the observation at one-based rank
`ceil(0.99 * N)` after all `N` observations are sorted. A service-wide p99 must
therefore be selected after combining mergeable distribution data. Averaging
the p99 values reported by workers does not compute the p99 of their union,
even when the average is weighted by worker request count.

The running counterexample has 1,000 observations on shard A and 10 on shard B.
Shard A contains 990 values at 1 microsecond and 10 at 100 microseconds. Shard B
contains 10 values at 1,000 microseconds. Using the nearest-rank definition,
their local p99 values are 1 and 1,000 microseconds. The union's p99 is 100
microseconds. The unweighted local-p99 average is 500.5 microseconds, and the
count-weighted average is about 10.891 microseconds. Both are wrong because a
percentile is a position, not an additive subtotal.

## Preserve the merge contract

A histogram groups observations into buckets. Its **schema** is the ordered set
of bucket boundaries and all rules that give the counts meaning. This crate's
interval histogram assigns each observation to one bucket: the first bucket
ends at the first inclusive upper bound, and each later bucket covers the
interval after the previous bound through its own inclusive upper bound.
`CumulativeHistogram` is cumulative over reporting time, not across bucket
boundaries: each entry is one interval bucket's monotonically increasing
counter from one producer. Merge corresponding counts only when the schemas,
units, population filters, and time semantics agree.

This crate makes the local invariants executable:

- `IntervalHistogram::merge_compatible` rejects unequal boundaries and count
  overflow before changing the destination.
- `CumulativeHistogram::delta_since` rejects a counter reset or a schema change
  before producing a time-window delta.
- `nearest_rank_bracket` returns the observed bucket interval `(lower, upper]`.
  It does not invent an exact value within a bucket.
- `coarsen` combines complete source buckets only when every target boundary is
  already present. It cannot recover detail discarded by a producer.

Run the deterministic example:

```bash
cargo run --release --package tail-latency-histogram-merge-errors \
  --example histogram_merge_probe
```

The exact union and the equal-schema histogram both place p99 in `(10, 100]`
microseconds. The program also proves that a mismatched schema and a cumulative
counter reset are rejected.

## Cost and error boundaries

Suppose there are `S` shards and `B` buckets per compatible histogram. Reading
every source histogram visits `S * B` counts. If the first shard becomes the
accumulator, combining the remaining shards performs `(S - 1) * B` checked
additions and stores `B` final counts. For this example, two shards and four
buckets require `2 * 4 = 8` count visits and `(2 - 1) * 4 = 4` merge additions.
The model supports capacity planning for aggregation work; it does not predict
elapsed time without a measured implementation and host.

Classic fixed buckets bound the answer to one interval. Here p99 lands after
the 10-microsecond boundary and no later than the 100-microsecond boundary, so
the honest answer is `(10, 100]` microseconds. Interpolation inside that bucket
adds a distribution assumption that the counts did not measure.

Compatible relative-error sketches and rank-error sketches solve different
problems. A relative-error sketch bounds error in the reported value. A
rank-error sketch bounds how far the selected rank may move. Neither repairs a
schema mismatch, mixed units, a counter reset, selection bias, or coordinated
omission in the data collection path.

## Evidence boundary

[`rounds/01.md`](rounds/01.md) defines the checked-source experiment. It runs
eight fresh correctness processes on each required Linux host and retains host,
toolchain, source, output, and generated-code receipts. The experiment does not
measure elapsed time; its fixed-size semantic check asks whether aggregation
preserves meaning.

The retained assembly for `topic44_checked_merge_four` shows how each exact
compiler and host lowered four checked additions. That output proves neither a
general instruction-set rule nor a latency advantage. The host notes under
[`measurements/`](measurements/) separate executed observations, source-backed
contracts, and inferred explanations.

The first retained run used source commit
`b8d0c8b06bd29dab090d40f18aa6aa086b5fdf76`. Each required host passed all eight
fresh processes and the checked-in receipt validator; both retrieved bundles
passed the validator again. See the
[cross-host comparison](measurements/2026-08-23-comparison.md) for the exact
host, toolchain, output, and generated-code boundaries.

## Selection guide

1. Keep raw observations when exact arbitrary queries and their storage cost are
   acceptable.
2. Use fixed buckets when the service-level threshold is known and every
   producer can use one explicit schema.
3. Use a mergeable relative-error sketch when multiplicative value error is the
   useful contract across a wide positive range.
4. Use a rank-error sketch when uncertainty in rank is the useful contract.
5. Reject or explicitly normalize incompatible inputs before aggregation. Do
   not silently average percentiles or reinterpret bucket indexes.
6. Query a time-window delta before combining cumulative counters, and detect
   resets at each producer boundary.

The practical rule is simple: merge distributions under one explicit contract,
then select the percentile. A local percentile has already discarded the
information needed to reconstruct the union.

Primary sources and version boundaries are in [`references.md`](references.md).
