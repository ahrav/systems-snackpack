# Primary sources

- Boncz, Zukowski, Nes, [MonetDB/X100: Hyper-Pipelining Query Execution](https://www.cidrdb.org/cidr2005/papers/P19.pdf), CIDR 2005. Tuple dispatch versus whole-column intermediates and bounded vector processing. Historical experiments only.
- Leis, Boncz, Kemper, Neumann, [Morsel-Driven Parallelism](https://www-db.in.tum.de/~leis/papers/morsels.pdf), SIGMOD 2014. Pipeline tasks, NUMA placement, adaptive scheduling, and dependency handling. The local allocator is a small contract example, not a reproduction.
- Kersten et al., [Everything You Always Wanted to Know About Compiled and Vectorized Queries](https://www.vldb.org/pvldb/vol11/p2209-kersten.pdf), VLDB 2018. Workload-dependent execution tradeoffs; push/pull and compilation/vectorization are separate dimensions.
- [DuckDB execution format](https://duckdb.org/docs/lts/internals/vector), read 2026-10-02. Default 2048-row vectors and flat, constant, dictionary representations. This executable uses its own plain columns and does not call DuckDB.
