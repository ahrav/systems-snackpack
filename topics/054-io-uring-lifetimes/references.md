# Primary sources

Implementation snapshots below use Linux v7.1 and liburing commit
`e50e32a6b9030faba2e30fa0ba999571a0cffe28`. The host receipts will record each
exact running kernel release. Version-based support claims still require a
direct setup, opcode, or registration probe.

- [`io_uring_setup(2)`](https://man7.org/linux/man-pages/man2/io_uring_setup.2.html)
  defines setup flags, including `SINGLE_ISSUER` and `DEFER_TASKRUN`.
- [Pinned liburing `io_uring_enter(2)`](https://github.com/axboe/liburing/blob/e50e32a6b9030faba2e30fa0ba999571a0cffe28/man/io_uring_enter.2)
  defines submission and event-entry behavior.
- [Linux v7.1 `io_uring.c`](https://github.com/torvalds/linux/blob/v7.1/io_uring/io_uring.c)
  implements setup, submitter ownership, and ring progress.
- [`io_uring_prep_cancel(3)`](https://man7.org/linux/man-pages/man3/io_uring_prep_cancel.3.html)
  defines async-cancel matching and result codes.
- [`io_uring_cancelation(7)`](https://man7.org/linux/man-pages/man7/io_uring_cancelation.7.html)
  explains cancellation races and file-reference behavior.
- [Linux v7.1 `cancel.c`](https://github.com/torvalds/linux/blob/v7.1/io_uring/cancel.c)
  implements cancellation.
- [`io_uring(7)`](https://man7.org/linux/man-pages/man7/io_uring.7.html)
  states the ordinary buffer-lifetime contract.
- [Pinned liburing `io_uring_register(2)`](https://github.com/axboe/liburing/blob/e50e32a6b9030faba2e30fa0ba999571a0cffe28/man/io_uring_register.2)
  defines registered-resource updates and retirement tags.
- [`io_uring_multishot(7)`](https://man7.org/linux/man-pages/man7/io_uring_multishot.7.html)
  defines `IORING_CQE_F_MORE` and terminal multishot CQEs.
- [Linux commit `b6b2bb58a754`](https://github.com/torvalds/linux/commit/b6b2bb58a75407660f638a68e6e34a07036146d0)
  changed auxiliary multishot overflow behavior in Linux 6.6.
- [Linux v6.12 UAPI header](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/io_uring.h)
  defines the constants used by the measured probe.

The `man7.org` pages mirror the Linux man-pages and liburing manuals. The
pinned repository links keep implementation-specific claims reviewable after
the projects change.
