# Primary references

- [Linux kernel NUMA memory policy](https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html)
  defines system, task, VMA, and shared policies; their scope and precedence;
  and the distinction between policy and page placement.
- [Linux kernel page migration](https://docs.kernel.org/mm/page_migration.html)
  describes page isolation, replacement allocation, copying, page-table
  updates, and migration failure conditions.
- [Linux kernel automatic NUMA balancing](https://docs.kernel.org/admin-guide/sysctl/kernel.html#numa-balancing)
  defines the system-wide control and the locality states the kernel samples.
- [`set_mempolicy(2)`](https://man7.org/linux/man-pages/man2/set_mempolicy.2.html),
  [`mbind(2)`](https://man7.org/linux/man-pages/man2/mbind.2.html), and
  [`get_mempolicy(2)`](https://man7.org/linux/man-pages/man2/get_mempolicy.2.html)
  define task and mapping policy calls, flags, fallback behavior, and error
  contracts.
- [`move_pages(2)`](https://man7.org/linux/man-pages/man2/move_pages.2.html) and
  [`migrate_pages(2)`](https://man7.org/linux/man-pages/man2/migrate_pages.2.html)
  define per-page status queries, explicit page movement, partial completion,
  and per-page error values.
- [Linux `/proc/<pid>/numa_maps`](https://docs.kernel.org/filesystems/proc.html#numa-memory-policy)
  documents the aggregate mapping view and its policy and node-count fields.
  The focused experiment uses per-page status because an aggregate does not
  prove every page's placement.
- [Linux cpuset version 1](https://docs.kernel.org/admin-guide/cgroup-v1/cpusets.html)
  defines allowed CPU and memory-node masks and their interaction with memory
  policies and migration.
- [`sched_setaffinity(2)`](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html)
  defines the CPU-affinity contract. Affinity constrains execution; it does not
  place existing pages.
- [Linux transparent huge pages](https://docs.kernel.org/admin-guide/mm/transhuge.html)
  documents global and per-mapping controls and the page sizes that can change
  the unit of placement and migration.
- [Intel 64 and IA-32 optimization reference manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel64-and-ia32-architectures-optimization.html)
  provides the vendor's NUMA locality and data-placement guidance. Vendor
  guidance identifies mechanisms and candidate controls; it does not replace a
  workload measurement on the exact processor.
