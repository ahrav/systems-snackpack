# Primary sources

- [Vyukov bounded MPMC queue](https://sites.google.com/site/1024cores/home/lock-free-algorithms/queues/bounded-mpmc-queue): sequence lifecycle, power-of-two original capacity, and explicit progress limitation.
- [Crossbeam 0.3.12 implementation](https://docs.rs/crossbeam-queue/0.3.12/src/crossbeam_queue/array_queue.rs.html): acquire/release slot stamps, sequentially consistent cursor operations, full/empty checks and unpublished-head retry. Its lap encoding differs from the model.
- [Crossbeam 0.3.12 API](https://docs.rs/crossbeam-queue/0.3.12/crossbeam_queue/struct.ArrayQueue.html): capacity, ownership on rejection and overwrite behavior.
- [Rust atomic ordering](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html): release/acquire synchronization and relaxed access limits.
- [Rust VecDeque](https://doc.rust-lang.org/std/collections/struct.VecDeque.html): a growable ring requiring a separate logical capacity check.
- [Crossbeam bounded channels](https://docs.rs/crossbeam-channel/latest/crossbeam_channel/fn.bounded.html): bounded multi-producer multi-consumer channel alternative.

Retrieved 2026-10-15. Performance conclusions come only from the retained runs.
The publication-hole history and capacity arithmetic are lesson analysis.
