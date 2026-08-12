# Primary sources and boundaries

## Operating-system durability contract

- Linux [`write(2)`](https://man7.org/linux/man-pages/man2/write.2.html)
  distinguishes accepted writes from later writeback errors.
- Linux [`fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html)
  defines `fsync`, `fdatasync`, and the separate directory-sync requirement.
- Linux [`open(2)`](https://man7.org/linux/man-pages/man2/open.2.html) documents
  direct and synchronized I/O flags and their filesystem-dependent limits.
- Linux [writeback cache control](https://docs.kernel.org/block/writeback_cache_control.html)
  defines preflush and Force Unit Access (FUA). FUA means that completion of
  one write includes stable-media semantics for that write.
- The ext4 [journal documentation](https://docs.kernel.org/filesystems/ext4/journal.html)
  explains ordered data mode, journal checksums, commit records, and barriers.

These interfaces specify the software contract. This topic does not verify
that a virtual controller or physical device survives power removal correctly.

## PostgreSQL 18 mechanics

- [WAL introduction](https://www.postgresql.org/docs/18/wal-intro.html) states
  the write-ahead rule and explains why data pages need not be forced at commit.
- [WAL configuration](https://www.postgresql.org/docs/18/wal-configuration.html)
  covers group commit, `commit_delay`, checkpoints, full-page images, and
  checkpoint completion targets.
- [Asynchronous commit](https://www.postgresql.org/docs/18/wal-async-commit.html)
  defines the acknowledgement and loss boundary.
- [WAL reliability](https://www.postgresql.org/docs/18/wal-reliability.html)
  describes flush requirements and lying write caches.
- [WAL internals](https://www.postgresql.org/docs/18/wal-internals.html)
  describes page LSNs, redo, segment files, and full-page images.
- [Data checksums](https://www.postgresql.org/docs/18/checksums.html) explains
  page checksums and their block-number input.
- PostgreSQL 18 [`xact.c`](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/access/transam/xact.c)
  flushes through the transaction's last WAL record before synchronous commit
  status publication.
- PostgreSQL 18 [`xlog.c`](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/access/transam/xlog.c)
  implements WAL insertion, writing, flush locks, grouping, and checkpoints.
- PostgreSQL 18 [`xlogrecord.h`](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/include/access/xlogrecord.h)
  defines the fixed WAL record header and CRC-32C field.
- PostgreSQL 18 [`xlogreader.c`](https://github.com/postgres/postgres/blob/REL_18_STABLE/src/backend/access/transam/xlogreader.c)
  validates record length, resource manager, previous-record pointer, and
  CRC-32C before trusting a record.

The cited implementation claims are bounded to the `REL_18_STABLE` source as
retrieved for this round. The Rust crate copies neither PostgreSQL's record
format nor its recovery algorithm.

## Recovery model and failure research

- The [ARIES paper](https://research.ibm.com/publications/aries-a-transaction-recovery-method-supporting-fine-granularity-locking-and-partial-rollbacks-using-write-ahead-logging)
  formalizes write-ahead logging with steal/no-force buffer management.
- The [ALICE paper](https://www.usenix.org/conference/osdi14/technical-sessions/presentation/pillai)
  derives crash states from system-call traces and shows why tested persistence
  assumptions must be explicit.
- [Can Applications Recover from `fsync` Failures?](https://www.usenix.org/conference/atc20/presentation/rebello)
  measures filesystem error-reporting behavior and motivates poisoning a failed
  durability generation rather than retrying blindly.

The cost equations in this topic are analytical decision models. They are not
claims made by these sources and are not PostgreSQL performance measurements.
