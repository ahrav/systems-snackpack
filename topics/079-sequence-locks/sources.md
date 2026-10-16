# Sources

Checked 2026-10-16. The experiment pins Rust 1.93.1; the online API pages may show
a newer release. The ordering and locking contracts below apply to the APIs used.

- [Linux sequence counters and sequential locks](https://docs.kernel.org/locking/seqlock.html): even/unchanged validation, writer serialization, delayed-writer hazards, conditional locking readers and separate pointer lifetime concerns.
- [Rust atomic ordering](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html): SeqCst total ordering. This crate uses SeqCst on payload fields as well as the sequence.
- [Rust undefined behavior](https://doc.rust-lang.org/reference/behavior-considered-undefined.html): data races remain undefined even when a result is discarded.
- [Rust volatile reads](https://doc.rust-lang.org/std/ptr/fn.read_volatile.html): volatile does not provide thread synchronization.
- [Rust RwLock](https://doc.rust-lang.org/std/sync/struct.RwLock.html): shared readers, exclusive writer and unspecified priority policy.
- [Boehm, MSPC 2012](https://research.google/pubs/can-seqlocks-get-along-with-programming-language-memory-models/): bibliographic pointer to language-model treatment of seqlocks; no implementation claim here depends on an unread paper body.

The proof, independent schedule oracle, retry-cost examples and measurement
selection rule are this lesson's analysis. Under independent equal-cost attempts,
expected attempts equal 1/q. Correlated failures behind an odd writer violate
that model. The illustrative exp(-lambda * r) success probability assumes Poisson
instantaneous writes and a fixed read interval; measured retries replace those
assumptions for this experiment.
