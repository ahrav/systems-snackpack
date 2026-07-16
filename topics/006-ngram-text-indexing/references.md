# References

- [Russ Cox, “Regular Expression Matching with a Trigram Index”](https://swtch.com/~rsc/regexp/regexp4.html) — Derives sound Boolean trigram filters for regular expressions and uses exact verification after candidate generation.
- [Google Code Search chapter](https://abseil.io/resources/swe-book/html/ch17.html#search-index) — Records the implementation evolution from fixed trigrams through suffix arrays to sparse n-grams. Its scale and latency figures describe Google’s system.
- [Zoekt design](https://github.com/sourcegraph/zoekt/blob/main/doc/design.md) — Documents positional trigrams, selective anchors, UTF-8 offset mapping, shard layout, and implementation-specific space measurements.
- [PostgreSQL `pg_trgm`](https://www.postgresql.org/docs/current/pgtrgm.html) — Defines PostgreSQL’s word padding, punctuation, similarity, GiST, GIN, `LIKE`, and regex semantics. These are not generic byte-substring semantics.
- [PostgreSQL GIN](https://www.postgresql.org/docs/current/gin.html) — Defines key-to-row posting lists, posting trees, operator strategies, and pending-list behavior.
- [Apache Lucene 10.3.1 `NGramTokenizer`](https://lucene.apache.org/core/10_3_1/analysis/common/org/apache/lucene/analysis/ngram/NGramTokenizer.html) — Defines code-point gram and source-offset behavior for that release.
- [Zobel, Moffat, and Sacks-Davis, VLDB 1993](https://www.vldb.org/conf/1993/P290.PDF) — Evaluates compressed n-gram inverted files, posting order, and the intersection-to-verification crossover on its recorded lexicon and hardware.
- [Ukkonen, 1992](https://www.cs.helsinki.fi/u/ukkonen/TCS92.pdf) — Develops occurrence-count q-gram filtering for approximate string matching.
- [Unicode Standard Annex #15](https://unicode.org/reports/tr15/) — Defines normalization forms and their concatenation and substring properties.
- [Unicode Standard Annex #29](https://unicode.org/reports/tr29/) — Defines Unicode text segmentation, including extended grapheme clusters.
