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

The exact model here is a reachable, deterministic, acyclic, partial byte
acceptor. An acceptor answers whether a byte string belongs to the dictionary.
Every stored state is reachable from the start, each state has at most one
transition for each byte, and stored transitions contain no cycle. "Partial"
means that a missing transition rejects without storing a rejecting sink. A
total transition table would add one non-final sink with 256 self-loops; this
artifact omits that cyclic state from its model and counts.

After either `b` or `c`, the legal remaining strings are exactly `ar` and
`at`. The two prefixes therefore have the same **right language**, the set of
suffixes that complete an accepted key.

For this model, process children before parents and identify a state by this
signature:

```text
(final flag, sorted [(input byte, canonical child ID)])
```

The final flag records whether the empty suffix is accepted. The byte labels
record the available next inputs, and each canonical child ID names an already
minimized target. Two reachable states merge exactly when all three parts
match. The builder retains a complete signature registry and checks that the
final graph has no duplicate reachable signatures. That establishes exact
state minimality for this acceptor model, not minimum encoded bytes.

This crate uses a batch bottom-up builder: it constructs the full trie, then
minimizes every state child before parent. This differs from the sorted
frontier algorithm, which minimizes only the completed suffix of the previous
key after that suffix leaves the shared frontier. Premature merging breaks
incremental insertion. After inserting `abd` and `bad`, the states after `ab`
and `ba` both accept only `d`. If a builder merges them, adding `bae` mutates
the shared state and wrongly accepts `abe`. This is a confluence failure: one
mutable state has acquired two incoming prefixes.

An output-bearing transducer needs a stronger equivalence rule. A sequential
finite-state transducer (FST) consumes input deterministically and maps each
accepted input to at most one output assembled along its path. A subsequential
FST also permits a final output emitted after the last input. For string
outputs, push common output prefixes to a consistent location, then compare
the residual output function: every remaining input suffix must reject at both
states or accept at both and emit the same remaining string, including the
final output. Other output types require their algebra's common-factor and
residual operations; string-prefix reasoning does not apply automatically.
Equal accepted suffix keys alone cannot justify an output-state merge.

## Contract before representation

The dictionary contract must answer these questions:

- Are keys arbitrary bytes or normalized text?
- Which byte ordering feeds construction and lookup?
- Do duplicate keys fail, replace, combine, or retain multiple values?
- Does one input have at most one output?
- Does the API perform exact lookup, seek, common-prefix search, predictive
  enumeration, suffix search, or fuzzy traversal?
- Can updates wait for an immutable rebuild?

Unicode normalization, collation, and duplicate resolution answer different
questions. Unicode Normalization Form C (NFC) composes canonically equivalent
sequences. Normalization Form KC (NFKC) also applies compatibility mappings, so
it can erase distinctions that NFC preserves. Collation assigns
language-sensitive weights for ordering; a collation tie is not automatically
the dictionary's identity rule. Duplicate resolution decides whether keys that
share the chosen identity fail, replace, combine, or retain multiple values.
Apply the same identity rule to queries, resolve duplicates under that rule,
then sort the resulting bytes in the builder's declared order. This crate uses
arbitrary byte keys and strict bytewise ordering. It implements neither Unicode
normalization nor collation.

| Representation | Problem solved | What it does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- |
| Hash table | Mutable exact lookup | Order or prefix traversal | Hash-table and allocation overhead | Updates and point lookup dominate |
| Sorted key array | Simple static membership | Shared structure | Comparisons revisit key bytes | The dictionary is moderate and simplicity wins |
| Trie or radix trie | Prefix sharing and traversal | Equal-future sharing | Child storage and pointer locality | Prefix operations or mutation dominate |
| Exact minimal DAFSA | Static membership with repeated residual languages | Values or cheap mutation | Batch build and immutable publication | Measured state sharing justifies the lifecycle |
| Sequential or subsequential FST | Functional key-to-output mapping | Arbitrary one-to-many relations | Residual-output equivalence depends on the output algebra | Outputs can be factored without changing meaning |
| Double-array trie | Indexed flat transitions | Dense packing | Empty slots and static construction | Direct transition lookup outweighs packing cost |
| Succinct trie | Small tree topology | Shared directed-acyclic-graph targets | Labels and navigation indexes remain | Tree topology is the main byte cost |

Suffix-state sharing saves storage but does not create a suffix-query index:
transitions still consume bytes from the key's start. Predictive enumeration is
output-sensitive. Returning `z` keys containing `y` total bytes requires at
least proportional work, written `Ω(z + y)`, to identify and emit them.
Fuzzy search instead traverses a product automaton whose state pairs one
dictionary state with one edit-distance state. Its work follows the reachable
state pairs, transitions, and emitted results; minimization alone does not
provide fuzzy lookup.

## Cost model

For a query with `m` bytes, let `r <= m` be the number of bytes whose outgoing
transition is searched before the first missing transition or the end of the
query. Let `d_i` be the fanout at the state searched for byte `i`, and let
`S(d_i)` be that state's arc-search cost. Approximate exact lookup as:

```text
lookup time ~= sum from i=1 to r of
    (state decode + S(d_i) + target decode when found + memory penalty)
    + final-state test when all m transitions exist
    + output decode and emission
```

For positive fanout, a linear label scan has worst-case `S(d) = Theta(d)`
comparisons and binary search has `S(d) = Theta(log(d + 1))`; an empty fanout
rejects in constant time. A direct table also has constant-time indexing but
spends space and cache footprint. Packed arcs save bytes but add decoding.
Early misses reduce `r`, so the same `O(m)` worst-case bound can hide different
work. If a successful lookup emits `y` output bytes, materializing those bytes
costs at least `Ω(y)` even when graph traversal is shorter.

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
- Lucene 10.4.0 uses a pluggable output algebra and several version-specific
  encoded traversal cases, including ordinary arc traversal and fixed-length
  binary-search, direct-addressed, and continuous-label cases. These are
  Lucene 10.4.0 implementation choices, not universal FST layouts.
- OpenFST 1.8.5 targets general weighted-automata algebra. Its representations
  and minimization algorithms have semiring and transducer preconditions.
- Memory mapping avoids an eager copy. It guarantees neither page residency nor
  safe in-place mutation. Publish a mapped dictionary by writing a new immutable
  versioned file in the target directory, validating its format and checksums,
  calling `fsync` on the file, renaming it into place on the same filesystem,
  and calling `fsync` on the containing directory. Publish the new mapping only
  after validation, and retain old mappings until their readers finish. Never
  overwrite or truncate a file while readers map it.

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
The timed misses are late misses: each traverses every byte of an existing key,
then fails on one appended byte. Early- and middle-byte misses appear only in
correctness checks, outside the timed query mix.

Run correctness from the repository root:

```bash
cargo test --locked --package finite-state-transducers-compact-dictionaries

cargo run --locked --release \
  --package finite-state-transducers-compact-dictionaries \
  --bin dictionary-probe -- verify
```

Run the fresh-process comparison on Linux. The runner requires Python's
`sched_getaffinity` and `sched_setaffinity` interfaces so every child process
uses one allowed CPU; platforms without those interfaces fail before timing.

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
mean complete-block log contrast. The reported sample standard deviation is on
the log-contrast scale and covers block-to-block variation in that run window.
It does not cover other machines, compilers, corpora, or future runs.

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
