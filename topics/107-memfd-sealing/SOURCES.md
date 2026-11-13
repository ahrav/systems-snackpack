# Primary sources

Read 2026-11-13.

- [memfd_create](https://man7.org/linux/man-pages/man2/memfd_create.2.html): backing, creation flags, publication and truncation hazards.
- [File seals](https://man7.org/linux/man-pages/man2/F_ADD_SEALS.2const.html): WRITE versus FUTURE_WRITE, size seals, seal-policy lock, errors.
- [mmap](https://man7.org/linux/man-pages/man2/mmap.2.html): shared/private mappings and descriptor lifetime.
- [Linux v6.12 implementation](https://github.com/torvalds/linux/blob/v6.12/mm/memfd.c): seal installation and outstanding references.
- [Linux v6.12 selftests](https://github.com/torvalds/linux/blob/v6.12/tools/testing/selftests/memfd/memfd_test.c): operation-level contracts.
