# Topic 9: Succinct and static index structures

A static index moves work from queries into construction. A succinct index
stores an object near its information-theoretic minimum while retaining the
required operations. These are separate claims: immutability enables more
layouts, but does not make a representation succinct.

## Representation first

For an arbitrary bitvector of length `N`, the raw payload is `N` bits. For a
set of exactly `m` positions drawn from a universe of size `N`, the counting
lower bound is:

```text
B(N, m) = ceil(log2(binomial(N, m))) bits
```

Every byte count must name its denominator. A minimal perfect hash function
can approach 1.44 bits per stored key, but that excludes keys, values, and
non-member verification. A wavelet matrix with plain bitmaps uses about
`N * ceil(log2(sigma))` payload bits before rank metadata. Elias-Fano targets a
monotone sequence and uses at most
`m * ceil(log2(N / m)) + 2m` bits before auxiliary indexes. These structures do
not implement interchangeable contracts.

## Focused rank directory

This crate compares two exact implementations of:

```text
rank1(pos) = number of one bits in the half-open range [0, pos)
```

`CompactRank` stores the original words, one 32-bit cumulative count per 512
input bits, and one 16-bit within-superblock count per 64-bit word. Its heap
representation uses 1.3125 bits per input bit for aligned large inputs:

```text
payload                = 1 bit per input bit
superblock directory   = 32 / 512 = 0.0625 bits per input bit
word directory         = 16 / 64  = 0.25 bits per input bit
total                  = 1.3125 bits per input bit
```

`PrefixRank` stores one 32-bit answer for every position. The table itself can
recover each source bit from adjacent differences, so it does not retain a
second payload copy. It is the correctness oracle, not a plausible production
design.
The compact query performs three dependent indexed loads, a mask, and a
population count. The prefix query performs one indexed load. The experiment
therefore tests whether the smaller working set repays extra query work.

The directory overhead is a fixed fraction of `N`, not `o(N)`. This teaching
layout is compact relative to the oracle but is not formally succinct. A true
succinct rank structure uses larger and recursively indexed regions, tables,
or compressed blocks so the auxiliary term is sublinear.

## Selection rules

| Required contract | Suitable starting point | Main cost to verify |
| --- | --- | --- |
| Dense bitmap membership plus rank/select | Plain bitmap with rank directory; RRR when density entropy matters | Directory traffic, block decode, and select sampling |
| Sorted sparse integers | Elias-Fano | Density, predecessor contract, and upper-bit select support |
| Sequence rank/select/access | Wavelet matrix or wavelet tree | Alphabet height, bitmap representation, and per-level locality |
| Static key-to-slot mapping | Minimal perfect hashing | Key fingerprint or membership layer, construction memory, and failure/retry policy |

RRR compresses by block population. It does not model long runs beyond their
effect on block populations. Elias-Fano needs a monotone sequence. A plain
wavelet matrix is an index layout, not automatically compressed. An MPHF maps
stored keys without collisions but gives arbitrary answers for non-members.

## Failure boundaries

- Do not infer latency from bits per key. Decode work and independent cache
  misses can dominate a smaller representation.
- Do not treat `O(1)` as one memory access. It only bounds the number of
  word-RAM operations independently of `N`.
- Do not benchmark construction inside the steady-state query timer.
- Do not count repeated inner-loop queries as independent samples. This
  experiment uses fresh processes as replication units.
- Do not infer an instruction from Rust's `count_ones` semantics. Inspect the
  linked binary built with the shipping target flags.
- Do not compare structures without matching the query contract, membership
  semantics, and stored payload.

## Run

Check every answer against the prefix oracle:

```bash
cargo run -p systems-snackpack-topic-009 --example check_equivalence
cargo bench -p systems-snackpack-topic-009 --bench succinct_rank -- --verify
```

Run 12 fresh, order-balanced process pairs on Linux:

```bash
topics/009-succinct-static-index-structures/experiment/run_processes.sh \
  /tmp/systems-snackpack-topic-009 local candidate unknown
cat /tmp/systems-snackpack-topic-009/summary.txt
```

The default dataset contains `2^26` deterministic pseudo-random bits. Each
process builds both indexes, warms each variant with 262,144 queries, and then
performs 4,000,000 deterministic uniform random queries from `[0, N)` per
variant. Correctness checks cover the valid endpoint at `N`; the timer does
not. Timed query execution excludes dataset, index, query construction, and
warmup. External wall time includes parent-shell command substitution,
`taskset`, process startup and teardown, and captured output transfer.

The summarizer reports per-variant process distributions and paired
`PrefixRank / CompactRank` ratios. Its exact 96.1% median interval is the third
through tenth ordered ratio from 12 pairs, assuming independent, identically
distributed continuous pair ratios.

Inspect [Round 1](rounds/01.md), [measurement records](measurements/README.md),
and [primary sources](references.md) before interpreting a host result.
