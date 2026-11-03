# Query optimization and cardinality estimation

Correlated filters can change the join algorithm selected by a cost model.
This crate counts matching pairs of non-null `u32` keys. Duplicate occurrences
multiply. It compares a nested loop with a fresh hash frequency table.

Run from the workspace root:

```sh
cargo test -p topic097-query-optimization
cargo build --release -p topic097-query-optimization --example query_probe
python3 topics/097-query-optimization/experiment/run.py \
  --binary target/release/examples/query_probe --output results.json
```

On Linux add `--cpu 0` when CPU 0 is allowed. The harness checks both algorithms
against SQLite for all pairs of sequences of length zero through three over
three keys, plus 500 seeded cases with duplicates and extreme keys.

## Experiment contract

Each dataset has 10,000 customer rows and 4,096 order keys. Orders repeat each
key in 0..1024 four times. Customer join keys are row index modulo 1024.
Filters select `a=1 AND b=1` before the timed join.

| Dataset | a | b | Independent estimate | Actual selected | Join count |
|---|---|---|---:|---:|---:|
| independent | i%100 | (i/100)%100 | 1 | 1 | 4 |
| correlated | i%100 | a | 1 | 100 | 400 |
| exclusive | i%100 | (a+1)%100 | 1 | 0 | 0 |
| dense | i%2 | a | 2500 | 5000 | 20000 |

The teaching model compares `outer*inner` with `10*(outer+inner)`. The factor
10 is illustrative and fixed before measurement. Exact joint counts are an
information upper bound; computing them by scanning is not a free optimizer
operation. Estimate generation and filtering are excluded from timings.

Each workload has eight fresh-process trials per algorithm in alternating
AB/BA order, plus one excluded warmup process per algorithm. Each process also
performs one untimed call. Fixed inner repetitions amortize clock overhead.
Hash build, randomized hash state, allocation, probing and destruction are
included in every call. Empty inputs return immediately in both paths.
Input generation, SQL checking, startup and output formatting are excluded.
The result contract is a count; materializing all matching pairs costs more.

Report medians, min/max, all samples and paired ratios. A workload winner must
exceed a 5% margin in every pair; otherwise label separation unresolved.
Linux affinity is fixed. Load, clocks, thermals and SMT are uncontrolled.
Fresh processes and randomized standard-library hash seeds retain process
variation. Fixed workload order and repeated warm data limit generalization.
PostgreSQL execution, indexed joins, cold storage and spilling need separate
measurements. See results.md for observed results and source identity.

## Sources

- [PostgreSQL 18 planner statistics](https://www.postgresql.org/docs/18/planner-stats.html): marginal and extended statistics, collection cost and limitations.
- [Multivariate examples](https://www.postgresql.org/docs/18/multivariate-statistics-examples.html): correlated equality filters and dependencies.
- [EXPLAIN](https://www.postgresql.org/docs/18/using-explain.html): costs, rows, loops and physical plans.
- [CREATE STATISTICS](https://www.postgresql.org/docs/18/sql-createstatistics.html): kinds and join-selectivity limitation.
- [Join planning](https://www.postgresql.org/docs/18/explicit-joins.html): legal orders and search costs.
- [Row estimation](https://www.postgresql.org/docs/18/row-estimation-examples.html): sampling, histograms and common values.
