# References

- [Linux page tables](https://docs.kernel.org/mm/page_tables.html) — Page-table hierarchy, folded levels, and huge-page entries.
- [Linux transparent huge pages](https://docs.kernel.org/admin-guide/mm/transhuge.html) — `MADV_HUGEPAGE`, multi-size THP, collapse, splitting, and verification boundaries.
- [Linux HugeTLB pages](https://docs.kernel.org/admin-guide/mm/hugetlbpage.html) — Reserved-pool semantics and HugeTLB interfaces.
- [Linux cache and TLB flushing](https://docs.kernel.org/core-api/cachetlb.html) — Kernel invalidation interfaces and ordering contract.
- [Linux x86 TLB documentation](https://docs.kernel.org/arch/x86/tlb.html) — Flush-range policy and collateral-refill tradeoff.
- [Linux `/proc` memory maps](https://docs.kernel.org/filesystems/proc.html) — `smaps` fields used to verify anonymous huge-page backing.
- [`madvise(2)`](https://man7.org/linux/man-pages/man2/madvise.2.html) — Linux `MADV_HUGEPAGE`, `MADV_NOHUGEPAGE`, and `MADV_COLLAPSE` contracts.
- [`mprotect(2)`](https://man7.org/linux/man-pages/man2/mprotect.2.html) — Protection-change semantics used by the shootdown workload.
- [Intel architecture manuals](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html) — Paging, PCID, `INVLPG`, and `INVPCID` architecture contracts.
- [AMD64 Architecture Programmer's Manual, Volume 2](https://docs.amd.com/v/u/en-US/24593_3.43) — AMD64 paging and TLB-control architecture contracts.
- [Arm memory-management guide](https://developer.arm.com/-/media/Arm%20Developer%20Community/PDF/Learn%20the%20Architecture/LearnTheArchitecture-MemoryManagement-101811_0100_00_en.pdf) — Translation tables, TLB maintenance, and barrier ordering.
- [Arm64 HugeTLB page sizes](https://docs.kernel.org/arch/arm64/hugetlbpage.html) — Linux arm64 huge-page size support by translation granule.
- [Kalibera and Jones, ISMM 2013](https://doi.org/10.1145/2464157.2464163) — Process-level replication and benchmark uncertainty.
