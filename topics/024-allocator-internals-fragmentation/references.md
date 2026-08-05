# References

- [Wilson et al., “Dynamic Storage Allocation: A Survey and Critical Review”](https://www.cs.hmc.edu/~oneill/gc-library/Wilson-Alloc-Survey-1995.pdf)
  separates allocator mechanism, fragmentation, and workload-sensitive policy.
- [glibc allocator](https://sourceware.org/glibc/manual/2.34/html_node/The-GNU-Allocator.html)
  describes the GNU allocator at the version boundary used by the lesson.
- [glibc allocation tunables](https://sourceware.org/glibc/manual/2.34/html_node/Memory-Allocation-Tunables.html)
  defines arena, tcache, mmap, and trim controls for glibc 2.34, the version
  recorded on both measured hosts.
- [glibc allocation statistics](https://sourceware.org/glibc/manual/2.34/html_node/Statistics-of-Malloc.html)
  defines `mallinfo2`, `malloc_info`, and their scope.
- [`malloc_trim(3)`](https://man7.org/linux/man-pages/man3/malloc_trim.3.html)
  defines the release request and its boolean return value.
- [Linux procfs](https://docs.kernel.org/filesystems/proc.html) defines the
  process residency fields sampled through `smaps_rollup`.
- [jemalloc](https://jemalloc.net/jemalloc.3.html),
  [TCMalloc](https://google.github.io/tcmalloc/design.html),
  [mimalloc](https://www.microsoft.com/en-us/research/publication/mimalloc-free-list-sharding-in-action/),
  and [Hoard](https://people.cs.umass.edu/~emery/pubs/berger-asplos2000.pdf)
  document alternative cache, arena, page, and ownership policies.
