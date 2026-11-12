# Sources checked 2026-11-11

- [Linux fork](https://man7.org/linux/man-pages/man2/fork.2.html): private views,
  COW, page-table work, child restrictions after multithreaded fork.
- [Kernel proc documentation](https://docs.kernel.org/filesystems/proc.html):
  mapping RSS, proportional sharing, private accounting and THP limits.
- [Linux madvise](https://man7.org/linux/man-pages/man2/madvise.2.html):
  MADV_NOHUGEPAGE and child-omission semantics of MADV_DONTFORK.
- [Kernel THP documentation](https://docs.kernel.org/admin-guide/mm/transhuge.html):
  page-size policy and observable mapping state.
- [glibc malloc source](https://codebrowser.dev/glibc/glibc/malloc/malloc.c.html#3157):
  tcache_put writes freed-chunk key/links and cache metadata. This source example
  establishes a write mechanism; the experiment measures synthetic flags.
- [Kernel overcommit](https://docs.kernel.org/mm/overcommit-accounting.html):
  commit accounting and fork admission.
- [Redis latency documentation](https://redis.io/docs/latest/operate/oss_and_stack/management/optimization/latency/):
  operational fork and post-fork costs. Historical timings apply to their setups.

For populated shared base pages retained by one child, additional backing is
page size times distinct parent-written pages, under the experiment's no-swap
conditions. Packed metadata can reduce this count. Separate measurements must
establish its access, lookup and concurrency costs in an application.
