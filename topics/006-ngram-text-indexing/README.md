# Topic 6: N-grams, trigrams, and text indexing

A document-level trigram index is a lossless candidate filter only when every
true match satisfies its gram condition and an exact matcher verifies survivors.
False positives cost time. False negatives violate an exact-search contract.

## Model the index and matcher separately

For document `d`, fixed gram size `g`, and byte offset `i`, the positional gram
set contains `(d[i..i+g], i)`. A document index drops the offset and records one
document ID per distinct gram. A positional index retains every occurrence.

For a literal of `m` bytes, `m - g + 1` overlapping grams exist when `m >= g`.
An exact occurrence implies that every query gram occurs at the required
relative offset. Document postings lose order and distance, so their
intersection only identifies candidates.

The executable example shows the distinction:

```bash
cargo run -p systems-snackpack-topic-006 --example check_equivalence
```

`abc---bcd` contains both trigrams from `abcd` but not the literal. The index
admits the document and the verifier rejects it.

## Cost model

For document lengths `L[d]`, a positional fixed-`g` index contains exactly:

```text
P = sum(max(0, L[d] - g + 1))
```

Document postings contain no more than `P` entries because repeated grams
collapse within each document.

For selected grams `S`, compressed posting bytes `b[t]`, candidate count `C`,
and verified bytes `V`:

```text
T_index ~= T_parse
        + sum(T_decode(b[t]))
        + T_intersect_or_probe
        + T_fetch(C)
        + T_verify(V)

T_scan  ~= T_read(corpus_bytes) + T_match(corpus_bytes)
```

The safe conjunction bound is `C <= min(df(t))`. Multiplying gram
selectivities assumes independence; overlapping grams and corpus structure
violate that assumption.

If index construction costs `T_build`, the query-count break-even is:

```text
Q > T_build / (T_scan - T_index)
```

This crossover exists only when the indexed query is faster. It excludes index
storage, updates, and retained generations.

## Choose the representation from the contract

| Technique | Use it for | Main cost |
|---|---|---|
| Direct scan | One-shot, short, common, or update-heavy search | Reads the corpus for each query |
| Word index | Token and relevance semantics | Misses arbitrary punctuation and infix matches |
| Document n-grams | Candidate documents plus exact verification | Common grams can retain a corpus-sized candidate set |
| Positional n-grams | Relative-offset pruning and occurrence locations | Larger postings and positional update work |
| Edge n-grams | Prefix and autocomplete search | Does not support arbitrary infix search |
| Suffix array or FM-style index | Static exact-substring lookup | Rebuild and query-expression complexity |
| Sparse or variable n-grams | Skewed postings or storage-resident indexes | Planner and format complexity |

Three is not a universal optimum. Increasing `g` can shorten postings, but it
increases distinct-key overhead and cannot filter patterns shorter than the gram
size. Measure compressed posting bytes, query lengths, candidate shrink,
verification bytes, and update amplification.

## Preserve text and query semantics

Bytes, Unicode scalar values, grapheme clusters, and tokens define different
indexes. Pin the unit and preprocessing version. Apply the same decoding,
normalization, case handling, and boundary rules at index, query, and verification
time. Preserve an offset map when normalized positions must identify original
text.

Regex extraction must retain a necessary Boolean condition for every accepting
path. Alternation needs union. Emptyable or short branches can force a scan.
The full regex matcher still verifies candidates.

## Focused experiment

The benchmark compares the same exact matcher under two access paths:

- scan every document;
- intersect distinct document-trigram postings, then verify candidates.

The 6 MiB deterministic corpus supplies 160 selective queries and 160
common/adversarial queries. The timer excludes corpus generation, index build,
four warm-up queries, process startup, and output.

Verify equivalence:

```bash
cargo bench -p systems-snackpack-topic-006 --bench selectivity -- --verify
```

Run one process per method:

```bash
cargo bench -p systems-snackpack-topic-006 --bench selectivity -- \
  --method scan --workload-order selective-first
cargo bench -p systems-snackpack-topic-006 --bench selectivity -- \
  --method index --workload-order selective-first
```

Run 12 order-balanced process pairs on Linux CPU 0:

```bash
topics/006-ngram-text-indexing/experiment/run_processes.sh /tmp/topic-006
```

Generate release assembly:

```bash
RUSTFLAGS='-C target-cpu=native -C debuginfo=1' \
  cargo rustc -p systems-snackpack-topic-006 --release --lib -- --emit=asm

rg -n 'scan_count|TrigramIndex.*query|bcmp|memcmp|xmm|ymm|zmm|sve' \
  target/release/deps/systems_snackpack_topic_006-*.s
```

Use process runs as replication units. Balance method and workload order. Record
the cpuset, compiler, flags, source hash, binary hash, candidate counts, build
time, and exact-result hashes. Keep cross-host results separate.

See the [measurement records](measurements/README.md), [source scopes](references.md),
and [first-round note](rounds/01.md).

The exact-source Linux runs passed on both required hosts. Selective queries
reduced candidate documents from 1,310,720 to 160. Common/adversarial queries
reduced none, and one host showed a workload-order reversal, so the artifact
does not report a host-independent common-query overhead.

## Failure checklist

- Scan or use a secondary index for patterns shorter than the gram size.
- Verify document-level candidates for order, distance, and multiplicity.
- Derive approximate-match thresholds from the stored presence, frequency, or
  position algebra. Do not switch representations by habit.
- Preserve regex alternation and emptyability in the gram query.
- Use one text pipeline and version across index, query, and verification.
- Resolve base segments, overlays, tombstones, and document generations in one
  snapshot.
- Budget decoded postings, candidates, verification, and regex work.
- Measure index memory, build amplification, and update latency at corpus scale.
