# Primary sources and version boundaries

The PostgreSQL links below target version 18 documentation or the PostgreSQL
18.4 `REL_18_4` source tag unless a different release is named.

## MVCC and isolation

- [Transaction isolation](https://www.postgresql.org/docs/18/transaction-iso.html)
  defines the three distinct isolation levels, statement and transaction
  snapshots, update rechecks, Snapshot Isolation anomalies, SSI behavior,
  predicate-lock observations, and retry requirements.
- [Transaction identifiers](https://www.postgresql.org/docs/18/transaction-id.html)
  defines 32-bit XID assignment, wraparound, freezing, and MultiXact identifiers.
- [System columns](https://www.postgresql.org/docs/18/ddl-system-columns.html)
  defines tuple `xmin`, `xmax`, and `ctid` and warns against using `ctid` as a
  durable row identifier.
- [Snapshot functions](https://www.postgresql.org/docs/18/functions-info.html#FUNCTIONS-PG-SNAPSHOT)
  defines the `pg_snapshot` text form and current `xid8` interfaces.
- [`snapshot.h`](https://github.com/postgres/postgres/blob/REL_18_4/src/include/utils/snapshot.h)
  states the exact MVCC snapshot bounds and in-progress arrays.
- [`heapam_visibility.c`](https://github.com/postgres/postgres/blob/REL_18_4/src/backend/access/heap/heapam_visibility.c)
  implements tuple visibility and shows the commit-status, in-progress, and
  hint-bit cases omitted by this crate.
- [PostgreSQL SSI paper](https://www.vldb.org/pvldb/vol5/p1850_danrkports_vldb2012.pdf)
  describes PostgreSQL 9.1's Serializable Snapshot Isolation implementation.
  Its mechanics remain useful; its 2011 performance results are not PostgreSQL
  18 measurements.
- [Serializable Snapshot Isolation paper](https://www.cs.cornell.edu/~sowell/dbpapers/serializable_isolation.pdf)
  derives the dangerous dependency structure used by SSI.

## HOT, pruning, and visibility

- [HOT updates](https://www.postgresql.org/docs/18/storage-hot.html) defines the
  index and same-page eligibility rules.
- [`README.HOT`](https://github.com/postgres/postgres/blob/REL_18_4/src/backend/access/heap/README.HOT)
  defines heap-only tuples, root redirects, pruning, index cleanup, and the
  page-local design.
- [`pruneheap.c`](https://github.com/postgres/postgres/blob/REL_18_4/src/backend/access/heap/pruneheap.c)
  implements page pruning and its cleanup-lock and page-pressure gates.
- [PostgreSQL 16 release notes](https://www.postgresql.org/docs/16/release-16.html)
  record HOT eligibility for BRIN-only indexed-column changes and the new
  `n_tup_newpage_upd` statistic.
- [Visibility map](https://www.postgresql.org/docs/18/storage-vm.html) defines
  the all-visible and all-frozen bits and which operations set or clear them.
- [Index-only scans](https://www.postgresql.org/docs/18/indexes-index-only-scans.html)
  explains why a clear all-visible bit forces a heap visibility check.

## Vacuum and observations

- [Routine vacuuming](https://www.postgresql.org/docs/18/routine-vacuuming.html)
  defines cleanup, statistics, visibility-map, freezing, wraparound, and
  autovacuum behavior.
- [`VACUUM`](https://www.postgresql.org/docs/18/sql-vacuum.html) defines standard
  and `FULL` behavior, locking, and options.
- [Vacuum configuration](https://www.postgresql.org/docs/18/runtime-config-vacuum.html)
  defines PostgreSQL 18 thresholds, worker limits, delay, and cost settings.
- [PostgreSQL 18 release notes](https://www.postgresql.org/docs/18/release-18.html)
  record the fixed maximum threshold, eager freezing, and cumulative vacuum
  time fields added in version 18.
- [Cumulative statistics](https://www.postgresql.org/docs/18/monitoring-stats.html)
  defines update counters, estimate and caching boundaries, and reset behavior.
- [VACUUM progress](https://www.postgresql.org/docs/18/progress-reporting.html#VACUUM-PROGRESS-REPORTING)
  defines phases, block counters, dead-tuple memory, index cycles, and delay time.
- [Replication slots](https://www.postgresql.org/docs/18/view-pg-replication-slots.html)
  defines `xmin` and `catalog_xmin` removal horizons held by slots.

The probability, update-work, debt-flow, and catch-up equations in this topic
are explicit analytical models. PostgreSQL does not expose them as planner or
autovacuum metrics.
