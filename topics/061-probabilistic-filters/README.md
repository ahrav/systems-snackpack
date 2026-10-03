# Probabilistic filters and streaming sketches

A cache service asks three separate questions: whether an object may exist,
how often an object was requested, and how many different objects were requested.
Membership, frequency, and distinct-count summaries have different error and
merge contracts. Exact catalog state remains authoritative.

```sh
cargo test -p topic061-probabilistic-filters
cargo run --release -p topic061-probabilistic-filters --example contracts
```

## Contract probe

The Rust models implement insertion-only Bloom membership and ordinary additive
Count-Min counters over canonical u64 keys. They reject incompatible dimensions
and seeds before merging. Count-Min rejects arithmetic overflow before mutation.
They do not implement persistence, concurrent publication, deletion, windowing,
serialization, or a production-quality independent hash family.

Tests check no false negatives for inserted members, union versus serial build,
merge compatibility, Count-Min upper bounds against exact frequencies, and
transactional overflow rejection. Negative controls show unsafe bit clearing,
duplicate snapshot aggregation, negative underlying counts, and saturation.
A register-maximum test illustrates union replay and lost provenance. It does
not implement or evaluate a HyperLogLog estimator.

The example uses 95,851 bits and seven Bloom probes. Sixteen fixed mixer seeds
insert 10,000, then 20,000 distinct keys. Each stage queries the same 100,000
known-absent keys, disjoint from both inserted populations. All inserted keys are
checked. These are 16 deterministic seed cases, not proof of independent random
trials. Inner queries and repeated host runs are not independent seed samples.
Count-Min uses width 272, depth 7, seed 42, and 1,000 exact known frequencies.

## Sizing and decision boundaries

Let n be inserted distinct keys, m filter bits, k probes, and p the absent-key
false-positive probability under the ideal hash approximation:

- p ~ (1-exp(-kn/m))^k. Here n=10,000, m=95,851, k=7 gives p~0.01004.
  At n=20,000 the same array gives p~0.15745. Overfilling hurts filtering utility.
- For Q requests, absent fraction a, filter cost Cf, and exact cost Ce, additive
  work is Q[ Cf + (1-a+ap)Ce ]. With Q=10 million, a=0.8, p=0.01004,
  Cf=0.1 microseconds and Ce=20 microseconds, this is 42.61 seconds of work
  versus 200 seconds without filtering. Costs are illustrative, not measured.
- For Count-Min error fraction epsilon=0.001 and fixed-query failure probability
  delta=0.000001, width ceil(e/epsilon)=2719 and depth ceil(ln(1/delta))=14
  require 304,528 bytes of eight-byte counters. The theorem needs its hash and
  nonnegative-frequency assumptions. Error epsilon*N at total mass N=10 million
  permits 10,000 additive error, not 0.1% relative error on a rare key.
- A classical HyperLogLog with M=16,384 registers has approximate asymptotic
  relative standard error 1.04/sqrt(M)=0.8125%. This is not a hard limit or an
  automatic confidence interval; implementation-specific estimators differ.

A fixed filter gives the same answer for repeated queries to the same key.
Query traffic frequency is not the number of independent hash trials. A
fixed-query sketch theorem does not automatically cover adaptive queries.

## Lifecycle selection

| Need | Candidate | Required boundary |
|---|---|---|
| Authoritative membership/count | Exact set/map | Memory and concurrency budget |
| Cheap negative lookup | Bloom | Filter covers the authoritative snapshot; verify positives |
| Matched insertion/deletion | Counting Bloom or cuckoo | Proven insertion membership, no overflow, handled insertion failure |
| Immutable membership | XOR filter | Construction retry/fallback and explicit rebuild |
| Supplied-key frequency | Count-Min | Nonnegative true frequencies, compatible hashes, no double ingestion |
| Distinct count/union | HyperLogLog | Compatible key/hash/register format and explicit time window |

Compatible Bloom OR and HyperLogLog register maximum are idempotent. Ordinary
Count-Min addition is not: replaying a worker snapshot counts it twice. Merged
Bloom occupancy depends on the union population, not the original per-shard
capacity. Adding final cardinality estimates double-counts shared keys.

Never infer safe cuckoo deletion from a possibly-positive lookup. Do not clear
ordinary Bloom bits to remove a key. Do not subtract ordinary HyperLogLog maxima
to expire a window. Time-bucket boundary error is separate from hash error.
Strict turnstile Count-Min can support signed updates while each true key
frequency remains nonnegative; this model deliberately only accepts additions.
Saturating counters avoid wrapping but can violate the frequency upper bound.

See [sources](references.md) and [evidence](measurements/README.md). This is a
correctness and empirical occupancy experiment. No timing or processor-family
performance comparison is made.
