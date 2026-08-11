# PostgreSQL MVCC, HOT updates, and vacuum debt

PostgreSQL keeps old row versions so readers can continue without seeing an
incomplete write. Those versions make concurrency practical, but they also
create index work and cleanup obligations. Correct isolation protects the
required invariant. Heap-only tuple (HOT) chains can reduce index work, and
maintenance capacity must keep cleanup debt within the system's operating
limit. A workload can remain healthy without HOT updates.

This crate is a deterministic mechanism model, not PostgreSQL. It represents
committed transaction identifiers, snapshots, one same-page HOT-like chain,
ordinary index-entry accounting, and a pinned cleanup horizon. It omits aborts,
subtransactions, command identifiers, wraparound and freezing, hint bits,
row-lock groups called MultiXacts, page headers and line-pointer redirects,
write-ahead logging, lock and index implementations, and background VACUUM
scheduling.

## One row, concurrent physical versions

Multiversion concurrency control (MVCC) lets an older and a newer physical
version of one logical row coexist. A transaction identifier (XID) names a
transaction for visibility checks; it is not a timestamp. An update records its
XID in the old version's `xmax` field and inserts a successor with a new `xmin`.
The old version's visibility ends only if the update commits; locks, aborted
updates, and MultiXacts give `xmax` other meanings.

A PostgreSQL snapshot records three relevant sets or bounds:

- `xmin`: XIDs below this bound finished before the snapshot;
- `xmax`: XIDs at or above this bound had not finished before the snapshot;
- `xip`: XIDs between those bounds that were still in progress.

The real visibility function also handles the current transaction, command
identifiers, aborts, subtransactions, hint bits, row locks, MultiXacts, and XID
wraparound. The crate deliberately excludes those cases. Its three committed
versions have visibility intervals `[10, 20)`, `[20, 30)`, and `[30, infinity)`.

## Isolation chooses which anomalies remain possible

PostgreSQL maps `READ UNCOMMITTED` to Read Committed, so it has three distinct
isolation implementations:

| Technique | Snapshot rule | Protects | Main catch |
| --- | --- | --- | --- |
| Read Committed | New snapshot for each statement | No dirty reads | A multi-statement transaction has no stable view. A modifying statement can wait and then recheck a newer row version. |
| Repeatable Read | One Snapshot Isolation view for the transaction | Stable reads and no phantoms in PostgreSQL | Write skew remains possible. A conflicting row update aborts the whole transaction. |
| Serializable | Snapshot Isolation plus Serializable Snapshot Isolation (SSI) dependency tracking | An outcome equivalent to at least one serial order | Error code `40001` requires whole-transaction retry. Broader read tracking can increase false positives. |

Snapshot Isolation means transactions read from a stable snapshot while
rejecting an update when its target changed after the snapshot. SSI tracks
read/write dependencies and aborts a transaction when they form a dangerous
structure associated with a possible serialization cycle. The nonblocking
`SIReadLock` predicate-lock mode used by SSI records reads without blocking
writers; those records help decide which transaction must abort. PostgreSQL can
combine fine-grained read records into broader ones when their memory budget
fills, which raises the chance of an unnecessary abort. `SERIALIZABLE READ ONLY
DEFERRABLE` can wait for a safe snapshot and then avoid serialization failures
for that read-only transaction.

## HOT avoids redundant ordinary index entries

A PostgreSQL update qualifies for HOT only when both conditions hold:

1. The update changes no column referenced by a non-summarizing index. Index
   keys, `INCLUDE` payloads, expression dependencies, and partial-index
   predicates all count.
2. The successor fits on the same heap page as the old version.

The Block Range Index (BRIN) is PostgreSQL 18's only core summarizing index.
Since PostgreSQL 16, changing only BRIN-indexed columns does not block HOT.

An ordinary index keeps one per-row entry pointing to the HOT chain's root item
identifier. A line pointer is the small page slot that implements that item
identifier. The heap versions point forward on the same page, and pruning can
turn the root line pointer into a redirect after old snapshots release
intermediate versions. PostgreSQL rejects cross-page HOT chains so pruning and
index lookup remain page-local.

`fillfactor` reserves heap-page space for later successors. Reducing it reserves
more free space for successors but enlarges the starting heap. A first-order
planning model is:

```text
p_hot = P(no changed non-summary-index column)
      * P(successor fits on the same page | index-eligible)

expected ordinary-index insertions per update
    ~= (1 - p_hot) * expected_applicable_ordinary_indexes
```

This is an analytical model, not a PostgreSQL planner equation. The applicable
index count varies with partial-index predicates, and summarizing indexes can
still need maintenance during a HOT update. Use the model to ask whether
avoided ordinary-index writes and future cleanup outweigh the larger heap.

## HOT changes debt shape; it does not remove vacuum

Page pruning can remove intermediate HOT versions during ordinary access, but
VACUUM still has distinct jobs:

- reclaim dead heap line pointers and ordinary index entries;
- set visibility-map bits that permit index-only scans to skip heap checks;
- freeze old XIDs before wraparound; and
- refresh planner statistics when requested.

Treat vacuum debt as separate ledgers rather than one counter:

```text
reclamation debt: obsolete versions, line pointers, index entries
visibility debt:  modified pages whose all-visible bit is clear
freeze debt:      old, unfrozen transaction and MultiXact identifiers
scheduling debt:  eligible work waiting for a worker, lock, or I/O budget
```

For reclamation debt `D`, obsolete-version creation rate `lambda_dead`, and
achieved useful removal rate `mu_effective`:

```text
dD/dt = lambda_dead - mu_effective
```

Debt stays constant when `mu_effective = lambda_dead` and grows when the removal
rate is lower. Draining a backlog requires `mu_effective > lambda_dead`;
provisioned service capacity needs headroom for variation. An old snapshot,
prepared transaction, or replication slot can pin the removal horizon and make
the achieved useful rate approach zero even while VACUUM runs.

PostgreSQL 18's background autovacuum scheduler makes an update/delete table
eligible for normal cleanup near:

```text
threshold = min(max_threshold, base_threshold + scale_factor * reltuples)
```

The defaults are `min(100,000,000, 50 + 0.2 * reltuples)`, where `reltuples` is
PostgreSQL's estimated live-row count for the relation. Eligibility does not
prove that a worker started, that versions are reclaimable, or that service
capacity exceeds creation rate.

## Observe the causes separately

`pg_stat_all_tables` update counters are cumulative, eventually consistent,
cached within a transaction by default, and resettable. Compare before-and-after
deltas from one declared counter horizon, refreshing the statistics snapshot as
needed:

```sql
SELECT
    n_tup_upd,
    n_tup_hot_upd,
    n_tup_newpage_upd,
    n_tup_upd - n_tup_hot_upd - n_tup_newpage_upd
        AS same_page_non_hot,
    n_tup_hot_upd::numeric / NULLIF(n_tup_upd, 0) AS hot_ratio
FROM pg_stat_user_tables
WHERE relname = 'target';
```

`n_tup_newpage_upd` counts successors placed on another page. It does not prove
that `fillfactor` alone caused every HOT miss: an indexed-column update can be
non-HOT even when its successor stays on the same page.

An `Index Only Scan` plan can still fetch heap tuples because ordinary indexes
do not store MVCC visibility. On an approved safe read or representative clone,
inspect `Heap Fetches` under `EXPLAIN (ANALYZE, BUFFERS)`. `EXPLAIN ANALYZE`
executes the statement. Data changes clear visibility-map bits; VACUUM sets
them when a page qualifies as all-visible.

Standard VACUUM normally returns space to the relation for reuse, not to the
operating system. `VACUUM FULL` rewrites the relation, needs extra disk, and
takes `ACCESS EXCLUSIVE`, PostgreSQL's strongest table lock, which blocks other
access while held.

## Run the model locally

From the repository root:

```bash
cargo test --locked --package mvcc-hot-vacuum
cargo build --locked --release --package mvcc-hot-vacuum \
  --bin mvcc-hot-vacuum-probe

target/release/mvcc-hot-vacuum-probe --self-check

python3 topics/032-mvcc-hot-vacuum/experiment/run_processes.py \
  target/release/mvcc-hot-vacuum-probe \
  /tmp/topic32-local

python3 topics/032-mvcc-hot-vacuum/experiment/validate_receipts.py \
  /tmp/topic32-local \
  target/release/mvcc-hot-vacuum-probe
```

The output directory must not exist. The runner launches eight fresh processes
and retains each exit status, standard output, standard error, and Secure Hash
Algorithm 256-bit (SHA-256) digest. The validator recomputes the expected
receipt instead of trusting the runner's summary.

No timing metric is reported. The model contains no PostgreSQL server, storage,
concurrency, or vacuum scheduler, so its elapsed time cannot rank database
designs.

See [`rounds/01.md`](rounds/01.md) for the acceptance contract,
[`measurements/README.md`](measurements/README.md) for the evidence boundary,
and [`references.md`](references.md) for versioned primary sources.
