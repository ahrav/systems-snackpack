# Primary sources

Read 2026-09-26. Wiki descriptions are design references, not proof of current
option defaults. No configuration defaults are prescribed by this artifact.

- [RocksDB compaction taxonomy](https://github.com/facebook/rocksdb/wiki/Compaction): leveled, tiered and hybrid structures; rewrite and overlap tradeoffs.
- [Leveled compaction](https://github.com/facebook/rocksdb/wiki/Leveled-Compaction): sorted runs, files and level shape.
- [Universal compaction](https://github.com/facebook/rocksdb/wiki/Universal-Compaction): run merging and input/output coexistence.
- [Write stalls](https://github.com/facebook/rocksdb/wiki/Write-Stalls): memtable, level-zero and pending-work conditions.
- [RocksDB tuning guide](https://github.com/facebook/rocksdb/wiki/RocksDB-Tuning-Guide): amplification boundaries and resource diagnosis.
- [LevelDB implementation](https://github.com/google/leveldb/blob/7ee830d02b623e8ffe0b95d59a74db1e58da04c5/doc/impl.md): overlap and immutable-file lifecycle.
- [LevelDB compaction source](https://github.com/google/leveldb/blob/7ee830d02b623e8ffe0b95d59a74db1e58da04c5/db/db_impl.cc): DoCompactionWork combines oldest-snapshot and IsBaseLevelForKey conditions. This crate models only single-key point-version retention; it does not reproduce the engine.
