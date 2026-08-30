# Primary references

## Application interfaces

- [`open(2)`](https://man7.org/linux/man-pages/man2/open.2.html) defines
  `O_DIRECT`, `O_DSYNC`, and their filesystem-dependent contracts. Interface
  boundary: Linux man-pages 6.18.
- [`statx(2)`](https://man7.org/linux/man-pages/man2/statx.2.html) defines
  `STATX_DIOALIGN`. Interface boundary: Linux man-pages 6.18.
- [`posix_fadvise(2)`](https://man7.org/linux/man-pages/man2/posix_fadvise.2.html)
  defines access-pattern advice and the best-effort `DONTNEED` behavior.
- [`readv(2)` and `preadv2(2)`](https://man7.org/linux/man-pages/man2/readv.2.html)
  define per-operation read flags, including `RWF_DONTCACHE` on Linux 6.14 and
  later.
- [`write(2)`](https://man7.org/linux/man-pages/man2/write.2.html) and
  [`fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html) separate
  buffered acceptance from data-integrity completion.
- [`mincore(2)`](https://man7.org/linux/man-pages/man2/mincore.2.html) reports
  memory residency for mapped pages.
- [`sync_file_range(2)`](https://man7.org/linux/man-pages/man2/sync_file_range.2.html)
  states that the call does not flush disk write caches or filesystem metadata
  needed for recovery.

## Linux mechanisms

- [Page cache](https://docs.kernel.org/7.1/mm/page_cache.html) defines the
  upstream Linux page-cache and folio model.
- [Virtual filesystem `address_space`](https://docs.kernel.org/7.1/filesystems/vfs.html#the-address-space-object)
  defines the file-offset to cached-memory mapping contract.
- [Memory-management API](https://docs.kernel.org/7.1/core-api/mm-api.html)
  documents read-ahead helpers and page-cache operations.
- [`mm/readahead.c`](https://github.com/torvalds/linux/blob/v7.1/mm/readahead.c)
  is the upstream Linux 7.1 read-ahead implementation used for explanatory
  mechanism claims.
- [`mm/page-writeback.c`](https://github.com/torvalds/linux/blob/v7.1/mm/page-writeback.c)
  is the upstream Linux 7.1 dirty-throttling and writeback implementation.
- [Virtual-memory sysctls](https://docs.kernel.org/7.1/admin-guide/sysctl/vm.html)
  define dirty thresholds and periodic writeback controls.
- [Control group version 2 writeback](https://docs.kernel.org/7.1/admin-guide/cgroup-v2.html#writeback)
  defines cgroup-aware writeback accounting and filesystem support limits.
- [`iomap` direct I/O](https://docs.kernel.org/filesystems/iomap/operations.html#direct-i-o)
  documents the direct-I/O path used by filesystems built on `iomap`.

The source links describe upstream Linux 7.1. The measured hosts ran Amazon
Linux kernels based on Linux 6.12, so source-level mechanism claims remain
explanatory unless the measurement records observe the behavior directly.
