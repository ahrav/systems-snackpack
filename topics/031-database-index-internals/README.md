# Database index internals

An index can avoid examining most rows, but it consumes memory, storage, and
write work. The useful question is not whether an index exists. It is which
pages a query must visit and which costs the chosen layout moves elsewhere.

This crate isolates one layout decision: a narrow secondary index followed by
a base-row fetch versus a wider covering index. A secondary index is a sorted
structure separate from the base rows. A covering index stores every value
needed by one query, so that query may avoid the base-row fetch.

The model is an in-memory search kernel, not a database engine. It has no page
cache, concurrent updates, transaction visibility, logging, compression, or
storage input/output.

## Page-budget mental model

The production ordered indexes discussed here belong to the B-tree family:
they store sorted entries in fixed-size pages and use upper pages to select a
child page. An internal page's **fanout** is the number of child ranges it can
name. Wider internal entries reduce fanout. Wider leaf entries reduce leaf
capacity; they reduce fanout only when the engine's internal entries also grow.

For usable page bytes `P`, fixed page overhead `H`, the relevant internal or
leaf entry bytes `E`, and target occupancy `alpha`, a first-order capacity
estimate is:

```text
maximum entries per page = floor((P - H) / E)
effective entries         = alpha * maximum entries per page
```

This is a planning bound, not an engine promise. Slot arrays, variable-length
keys, prefix compression, duplicate compression, fill policy, and split policy
change the actual result.

## The layout tradeoff

The experiment models a point query that finds one ordered key and returns two
payload values.

```text
narrow path:   binary-search (key, row locator) -> fetch payload[row locator]
covering path: binary-search (key, payload)     -> return payload in the entry
```

The narrow path searches fewer index bytes but adds an indirect payload read.
The covering path removes that read but makes every modeled leaf entry wider.
Both paths return identical values and report their logical structure sizes.

A covering layout is worthwhile when saved base-row reads outweigh the wider
index's cache and write costs. For `Q` matching reads and `W` index writes:

```text
Q * saved_base_fetch_cost
  > Q * extra_index_lookup_cost
  + W * extra_index_write_cost
  + extra_cache_pressure
```

Every term depends on the workload and engine. The inequality is a decision
frame, not a claim that this kernel measures production costs.

## Engine boundaries

- PostgreSQL 18 secondary B-tree leaves store tuple identifiers that locate
  heap rows. An index-only scan can still visit the heap unless the visibility
  map proves that the heap page is all-visible.
- InnoDB 8.4 secondary leaves store the row's primary-key columns. A
  non-covering lookup then searches the clustered primary index.
- SQLite 3 table and index B-trees use row identifiers or primary-key records
  according to the table format.

These locators and visibility rules are not interchangeable. The crate uses an
array position only to represent an unpredictable second lookup.

## Run locally

From the repository root:

```bash
cargo test --locked --package database-index-internals
cargo build --locked --release --package database-index-internals

target/release/index-layout-probe check

python3 topics/031-database-index-internals/experiment/run_processes.py \
  target/release/index-layout-probe \
  /tmp/topic31-local

python3 topics/031-database-index-internals/experiment/summarize.py \
  /tmp/topic31-local
```

On Linux, the runner uses `taskset` to pin fresh processes to one central
processing unit (CPU) when that command is available. It uses paired,
order-balanced blocks on every platform and excludes data construction and one
warmup pass from steady-state timing. The output directory must not exist.

See [`rounds/01.md`](rounds/01.md) for the experiment contract,
[`measurements/README.md`](measurements/README.md) for retained results, and
[`references.md`](references.md) for primary-source boundaries.
