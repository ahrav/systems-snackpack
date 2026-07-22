# Primary sources

- [`mmap(2)`](https://man7.org/linux/man-pages/man2/mmap.2.html): mapping,
  `MAP_POPULATE`, `SIGBUS`, and private/shared semantics.
- [`madvise(2)`](https://man7.org/linux/man-pages/man2/madvise.2.html):
  `MADV_DONTNEED`, `MADV_RANDOM`, and `MADV_POPULATE_READ/WRITE` contracts.
- [`mincore(2)`](https://man7.org/linux/man-pages/man2/mincore.2.html): residency
  vector and snapshot boundary.
- [`posix_fadvise(2)`](https://man7.org/linux/man-pages/man2/posix_fadvise.2.html):
  best-effort cache advice and partial-page behavior.
- [`getrusage(2)`](https://man7.org/linux/man-pages/man2/getrusage.2.html): minor
  and major process-fault counters.
- [`mlock(2)`](https://man7.org/linux/man-pages/man2/mlock.2.html): residency and
  retention contract.
- [`mbind(2)`](https://man7.org/linux/man-pages/man2/mbind.2.html): anonymous
  zero-page behavior and allocation-time NUMA policy.
- [Linux v6.18 page-table documentation](https://docs.kernel.org/6.18/mm/page_tables.html):
  hardware walk and shared fault-path model.
- [Linux v6.18 `mm/memory.c`](https://github.com/torvalds/linux/blob/v6.18/mm/memory.c):
  anonymous faults, common fault handling, retry-aware accounting, and
  fault-around implementation.
- [Linux v6.18 `mm/filemap.c`](https://github.com/torvalds/linux/blob/v6.18/mm/filemap.c):
  generic file-fault and page-cache paths.
- [Linux v6.18 NUMA memory policy](https://docs.kernel.org/6.18/admin-guide/mm/numa_memory_policy.html):
  first-touch placement boundaries.
- [Linux v6.18 transparent huge pages](https://docs.kernel.org/6.18/admin-guide/mm/transhuge.html):
  larger mappings and control interfaces.
- [Crotty, Leis, and Pavlo, CIDR 2022](https://db.cs.cmu.edu/papers/2022/cidr2022-p13-crotty.pdf):
  scoped DBMS evidence for mmap behavior under eviction and storage parallelism.

The interface ledger uses Linux man-pages 6.18 and upstream Linux v6.18.
Recorded hosts may run vendor kernels with backports, so host records retain the
exact kernel and observed generated code.
