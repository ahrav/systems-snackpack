# Finite-state transducers and compact dictionaries

A static dictionary must preserve exact key and value semantics while avoiding
repeated structure. A trie shares common key prefixes. A minimal deterministic
acyclic finite-state acceptor (DAFSA) also merges prefixes that permit the same
remaining suffixes. A finite-state transducer (FST) adds output to those paths.

These names do not select one storage layout. State minimization, serialized
bytes, resident memory, build cost, and lookup time are separate objectives.
Choose the key and query contract first, then measure the complete
representation on its real corpus.

## Equal futures, not similar-looking suffixes

For the keys `bar`, `bat`, `car`, and `cat`, a trie has nine states and eight
arcs. The exact minimal partial DAFSA has four states and five arcs:

```text
start --b,c--> q1 --a--> q2 --r,t--> q3(final)
```

After either `b` or `c`, the legal remaining strings are exactly `ar` and
`at`. The two prefixes therefore have the same **right language**, the set of
suffixes that complete an accepted key.

For an acyclic byte acceptor, process children before parents and identify a
state by this signature:

```text
(final flag, sorted [(input byte, canonical child ID)])
```

Two reachable states merge exactly when their signatures match. The builder in
this crate retains a complete signature registry and checks that the final
graph has no duplicate reachable signatures. That establishes exact state
minimality for this acceptor model. It does not establish minimum encoded
bytes.

An output-bearing transducer needs a stronger equivalence rule. Common output
prefixes must be pushed to a consistent location before comparing residual arc
and final outputs. Arbitrary leaf values cannot be ignored during
minimization.

## Contract before representation

The dictionary contract must answer these questions:

- Are keys arbitrary bytes or normalized text?
- Which byte ordering feeds construction and lookup?
- Do duplicate keys fail, replace, combine, or retain multiple values?
- Does one input have at most one output?
- Does the API perform exact lookup, seek, common-prefix search, predictive
  enumeration, suffix search, or fuzzy traversal?
- Can updates wait for an immutable rebuild?

Unicode Normalization Form C (NFC) and Normalization Form KC (NFKC) produce
different identities. Normalization must precede sorting and duplicate
resolution, and queries must use the same rule. This crate uses arbitrary byte
keys and strict bytewise ordering. It does not implement Unicode normalization
or collation.

| Representation | Problem solved | What it does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- |
| Hash table | Mutable exact lookup | Order or prefix traversal | Hash-table and allocation overhead | Updates and point lookup dominate |
| Sorted key array | Simple static membership | Shared structure | Comparisons revisit key bytes | The dictionary is moderate and simplicity wins |
| Trie or radix trie | Prefix sharing and traversal | Equal-future sharing | Child storage and pointer locality | Prefix operations or mutation dominate |
| Exact minimal DAFSA | Static membership with repeated residual languages | Values or cheap mutation | Batch build and immutable publication | Measured state sharing justifies the lifecycle |
| Sequential FST | Functional key-to-output mapping | Arbitrary one-to-many relations | Output algebra and duplicate semantics | Outputs can be factored without changing meaning |
| Double-array trie | Indexed flat transitions | Dense packing | Empty slots and static construction | Direct transition lookup outweighs packing cost |
| Succinct trie | Small tree topology | Shared directed-acyclic-graph targets | Labels and navigation indexes remain | Tree topology is the main byte cost |

Suffix-state sharing saves storage but does not create a suffix-query index.
Predictive enumeration also remains proportional to its emitted keys and
bytes, not only the prefix length.

## Cost model

For a key with `m` bytes, approximate exact lookup as:

```text
lookup time ~= sum over bytes of
    (state decode + arc search at that fanout + target decode + memory penalty)
    + output decode
```

An arc search can scan linearly, binary-search labels, or index a direct table.
A direct table spends bytes to reduce comparisons. Packed arcs save bytes but
add decoding. The same `O(m)` bound can therefore hide different costs.

Total bytes include:

```text
states + arcs + labels + targets + outputs + indexes + alignment + metadata
```

The teaching format reports `topology_bytes` as exactly:

```text
state_count * size_of::<State>() + arc_count * size_of::<Arc>()
```

It excludes vector headers, spare capacity, allocator metadata, source keys,
queries, and builder storage. Its `#[repr(C)]` records describe one Rust
binary's in-memory layout, not a portable file format.

For an immutable base with delta layers, include rebuild work:

```text
expected request cost ~= base lookup
                      + reached delta lookups
                      + rebuild_and_publish_cost / requests_between_rebuilds
```

This model supports a bounded-delta policy. An unbounded number of deltas turns
write avoidance into read amplification and tombstone debt.

## Production boundaries

- Rust `fst` 0.4.7 stores immutable byte sets and byte-to-`u64` maps. Its
  bounded state registry does not guarantee exact minimality. Nodes with at
  most 32 transitions use a linear label scan; wider nodes add a 256-byte
  direct index.
- Lucene 10.4.0 uses a pluggable output algebra and four arc layouts. A
  bounded suffix cache and fixed-arc settings trade build memory, bytes, and
  dispatch work.
- OpenFST 1.8.5 targets general weighted-automata algebra. Its representations
  and minimization algorithms have semiring and transducer preconditions.
- Memory mapping avoids an eager copy. It does not guarantee page residency or
  safe in-place mutation. Publish verified, immutable, versioned files and keep
  old mappings alive until their readers finish.

See [`references.md`](references.md) for primary sources and exact version
boundaries.

## Focused experiment

The probe compares a flat trie with an exact minimal DAFSA. Both variants use
the same eight-byte `State`, eight-byte `Arc`, and exported binary-search lookup
kernel. The comparison therefore changes graph topology and address stream,
not the lookup algorithm.

Two deterministic 65,536-key data sets expose different sharing:

- `shared`: every four-hex-digit prefix followed by `:metrics:v1`;
- `opaque`: fixed-seed, 16-byte SplitMix64-derived keys.

The primary timing mix contains 50% hits and 50% append-byte misses. Corpus
construction, graph construction, correctness checks, calibration, warmup,
process startup, and output stay outside the reported steady-state interval.

Run correctness from the repository root:

```bash
cargo test --locked --package finite-state-transducers-compact-dictionaries

cargo run --locked --release \
  --package finite-state-transducers-compact-dictionaries \
  --bin dictionary-probe -- verify
```

Run the fresh-process comparison:

```bash
RUSTFLAGS="-C target-cpu=native -C debuginfo=1" \
  cargo build --locked --release \
  --package finite-state-transducers-compact-dictionaries \
  --bin dictionary-probe

python3 -I \
  topics/035-finite-state-transducers-compact-dictionaries/experiment/run_processes.py \
  --binary target/release/dictionary-probe \
  --output /tmp/topic035-results \
  --blocks 12 \
  --aa-blocks 4 \
  --seed 350035 \
  --target-ms 200

python3 -I \
  topics/035-finite-state-transducers-compact-dictionaries/experiment/validate_receipts.py \
  /tmp/topic035-results
```

The output directory must not exist. Each treatment process selects one
method. Twelve complete `ABBA` or `BAAB` blocks compare the DAFSA with the trie;
four trie-versus-trie blocks check the schedule and analysis path. The runner
freezes calibration before the schedule. Inner lookups reduce timer noise but
do not increase the process-level run count.

The reported candidate-to-baseline point estimate is the exponential of the
mean complete-block log contrast. Its sample standard deviation covers
block-to-block variation in that run window. It does not cover other machines,
compilers, corpora, or future runs.

## Evidence boundary

- **Measured:** elapsed monotonic time, process wall time, state and arc counts,
  topology bytes, checksums, process order, host metadata, binary hashes, and
  linked instructions.
- **Derived and independently validated:** nanoseconds per lookup, complete-block
  log contrasts, geometric ratios, and sample standard deviations.
- **Source-backed:** minimal-state construction and the versioned library
  behavior in `references.md`.
- **Inferred:** cache, branch, prefetch, or page-fault mechanisms unless a
  separate counter or trace measures them.
- **Not tested:** output-bearing FST performance, Unicode identity, mapped-file
  startup, fuzzy search, updates, production corpora, or an instruction-set
  architecture family.

See [`rounds/01.md`](rounds/01.md) for the promotion contract and
[`measurements/README.md`](measurements/README.md) for retained evidence.
