# Primary sources

- [Linux man-pages6.19 futex](https://man7.org/linux/man-pages/man2/futex.2.html):
  aligned32-bit word, private/shared keying, userspace fast path.
- [FUTEX_WAIT](https://man7.org/linux/man-pages/man2/FUTEX_WAIT.2const.html):
  atomic compare-and-block, EAGAIN, EINTR, spurious return and relative timeout.
- [FUTEX_WAKE](https://man7.org/linux/man-pages/man2/FUTEX_WAKE.2const.html):
  positive wake counts1 and INT_MAX, returned count, no choice-of-waiter guarantee.
- [FUTEX_CMP_REQUEUE](https://man7.org/linux/man-pages/man2/FUTEX_CMP_REQUEUE.2const.html):
  compare, wake and move remaining waiters between kernel queues.
- [Rust1.93.1 futex mutex](https://github.com/rust-lang/rust/blob/1.93.1/library/std/src/sys/sync/mutex/futex.rs):
  three-state lock, contended acquisition and wake-one relay, bounded spin.
  The teaching lock is deliberately simpler.
- [Rust park](https://doc.rust-lang.org/std/thread/fn.park.html):
  per-thread token, spurious returns, intervening park consumes token.
- [Kernel PI futex](https://docs.kernel.org/locking/pi-futex.html):
  priority inheritance is a separate kernel/userspace protocol.

Read2026-10-06. Source claims are separate from the instrumented benchmark results.
