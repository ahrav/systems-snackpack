# Primary references

## Ordered pages and concurrency

- [PostgreSQL 18 database page
  layout](https://www.postgresql.org/docs/18/storage-page-layout.html) defines
  page headers, item identifiers, tuple space, and access-method-specific
  special space. The usual 8 KiB page size is a build-time default, not a
  universal B-tree constant.
- [PostgreSQL 18 B-tree
  indexes](https://www.postgresql.org/docs/18/btree.html) defines supported
  comparisons, ordering, uniqueness, deduplication, and implementation
  boundaries.
- PostgreSQL's [`nbtree` implementation notes for
  REL_18_STABLE](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/backend/access/nbtree/README)
  document high keys, sibling links, split repair, page deletion, locking, and
  the reasons the implementation differs from the original paper.
- Lehman and Yao, [*Efficient Locking for Concurrent Operations on B-Trees*
  (1981)](https://doi.org/10.1145/319628.319663), introduces right links and
  high keys for its concurrency model. It does not prove that production
  engines need no read latches, recovery protocol, or page reclamation.

## Covering and composite indexes

- [PostgreSQL 18 index-only scans and covering
  indexes](https://www.postgresql.org/docs/18/indexes-index-only-scans.html)
  explains `INCLUDE` payload columns and the heap visibility-map check.
- [PostgreSQL 18 multicolumn
  indexes](https://www.postgresql.org/docs/18/indexes-multicolumn.html) defines
  leading-column range bounds and PostgreSQL 18 B-tree skip scan.
- [InnoDB 8.4 clustered and secondary
  indexes](https://dev.mysql.com/doc/refman/8.4/en/innodb-index-types.html)
  defines clustered primary-key leaves and primary-key fields in secondary
  entries.
- [SQLite 3 file format](https://www.sqlite.org/fileformat2.html#b_tree_pages)
  defines table and index B-tree pages, cells, row identifiers, and overflow
  records.

## Competing access paths

- [PostgreSQL 18 bitmap index
  combination](https://www.postgresql.org/docs/18/indexes-bitmap-scans.html)
  describes bitmap `AND` and `OR`, heap-page ordering, and loss of index order.
- [PostgreSQL 18 hash
  indexes](https://www.postgresql.org/docs/18/hash-index.html) documents
  equality-only, lossy hash rechecks, bucket splits, and overflow pages.
- [PostgreSQL 18 Block Range Indexes
  (BRIN)](https://www.postgresql.org/docs/18/brin.html) documents lossy page-
  range summaries, physical correlation, and summarization maintenance.
- [PostgreSQL 18 Generalized Inverted Indexes
  (GIN)](https://www.postgresql.org/docs/18/gin.html) documents mapping
  component keys to posting lists for composite values such as arrays.
- [PostgreSQL 18 examining index
  usage](https://www.postgresql.org/docs/18/indexes-examine.html) requires
  realistic data and current statistics when interpreting planner choices.

## Artifact boundary

The references establish engine behavior and terminology. The artifact's
tests, process records, hashes, and disassembly validate only its deterministic
in-memory model. They do not validate a database engine or predict production
query performance.
