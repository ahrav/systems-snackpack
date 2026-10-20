# Sources checked 2026-10-20

- [Rust RwLock contract](https://doc.rust-lang.org/std/sync/struct.RwLock.html):
  concurrent readers, exclusive writer, unspecified admission, recursive-read
  hazard. Live page reports 1.99.1; measured compiler is separately pinned 1.93.1.
- [Rust 1.93.1 futex implementation](https://raw.githubusercontent.com/rust-lang/rust/1.93.1/library/std/src/sys/sync/rwlock/futex.rs):
  shared reader count, CAS acquisition, fetch-sub release, waiting flags. This
  backend is the implementation reference; glibc pthread policy is a different API.
- [parking_lot 0.12.5](https://docs.rs/parking_lot/0.12.5/parking_lot/type.RwLock.html):
  task fairness, eventual fair unlocking, recursive-read hazard. Not benchmarked.
- [glibc lock preferences](https://man7.org/linux/man-pages/man3/pthread_rwlockattr_setkind_np.3.html):
  reader preference and nonrecursive writer-preference option. Not benchmarked.
- [Linux RCU](https://docs.kernel.org/RCU/whatisRCU.html): separate replacement
  and reclamation; preserve old versions until earlier readers finish. Not benchmarked.

The three-request timeline is a derived policy model. The throughput expression
n/(C+A(n)) is a heuristic separating useful work and coordination. Neither is a
prediction fitted to the measured hosts. Atomic operations in source motivate a
coherence hypothesis but do not establish the cause of any measured slowdown.
