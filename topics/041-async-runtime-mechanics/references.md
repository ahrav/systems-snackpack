# Primary sources and version boundaries

Rust stable 1.97.1, Tokio 1.53.1, and `tokio-util` 0.7.19 are the documentation
boundaries for this visit. The measured Arm host used rustc 1.95.0. Compiler
future layout and Tokio task layout are not stable application binary
interfaces (ABIs); remeasure them after a toolchain or runtime change.

## Rust future mechanics

- [The `Future` trait](https://doc.rust-lang.org/1.97.1/std/future/trait.Future.html)
  defines nonblocking `poll`, `Ready`, `Pending`, and the current-waker rule.
- [The await expression](https://doc.rust-lang.org/1.97.1/reference/expressions/await-expr.html)
  defines conversion, pinning, polling, and suspension only on `Pending`.
- [Async blocks](https://doc.rust-lang.org/1.97.1/reference/expressions/block-expr.html#async-blocks)
  describe the compiler-generated future and captured values.
- [Pinning](https://doc.rust-lang.org/1.97.1/std/pin/)
  defines address-stability obligations and the distinction between a pointer
  and its pointee.
- [The `Waker` type](https://doc.rust-lang.org/1.97.1/std/task/struct.Waker.html)
  defines executor notification and wake coalescing.
- [Async/await RFC 2394](https://github.com/rust-lang/rfcs/blob/master/text/2394-async_await.md)
  supplies the conceptual state-machine model. Current standard-library
  documentation, not the RFC, governs behavior after completion.
- [Async-drop tracking issue 126482](https://github.com/rust-lang/rust/issues/126482)
  records the experimental, nightly-only status of asynchronous destruction.

## Tokio task and scheduler mechanics

- [Runtime and scheduler behavior](https://docs.rs/tokio/1.53.1/tokio/runtime/index.html)
  states the bounded fairness assumptions and labels queue details as current
  implementation behavior.
- [Task cell source](https://docs.rs/tokio/1.53.1/src/tokio/runtime/task/core.rs.html)
  shows the header, core stage, trailer, and overlapping future/output storage.
- [Task state source](https://docs.rs/tokio/1.53.1/src/tokio/runtime/task/state.rs.html)
  defines notification, completion, cancellation, and reference-count state.
- [Task waker source](https://docs.rs/tokio/1.53.1/src/tokio/runtime/task/waker.rs.html)
  shows how raw wakers update the task reference count and notification state.
- [`select!`](https://docs.rs/tokio/1.53.1/tokio/macro.select.html),
  [`join!`](https://docs.rs/tokio/1.53.1/tokio/macro.join.html), and
  [`try_join!`](https://docs.rs/tokio/1.53.1/tokio/macro.try_join.html)
  define inline concurrency, loser dropping, fairness controls, and documented
  cancellation-safe operations.
- [`JoinHandle`](https://docs.rs/tokio/1.53.1/tokio/task/struct.JoinHandle.html)
  defines detachment on drop and abort behavior.
- [`JoinSet`](https://docs.rs/tokio/1.53.1/tokio/task/struct.JoinSet.html)
  defines dynamic task ownership, abort, drain, and shutdown operations.
- [`yield_now`](https://docs.rs/tokio/1.53.1/tokio/task/fn.yield_now.html)
  documents its non-guarantees.
- [`timeout`](https://docs.rs/tokio/1.53.1/tokio/time/fn.timeout.html)
  documents that the future is polled before the deadline check.
- [`spawn_blocking`](https://docs.rs/tokio/1.53.1/tokio/task/fn.spawn_blocking.html)
  documents the non-abortable started-work boundary.

## Cooperative shutdown helpers

- [`CancellationToken`](https://docs.rs/tokio-util/0.7.19/tokio_util/sync/struct.CancellationToken.html)
  defines signaling, parent-to-child propagation, and cancellation races.
- [`TaskTracker`](https://docs.rs/tokio-util/0.7.19/tokio_util/task/task_tracker/struct.TaskTracker.html)
  defines the closed-and-empty completion condition and distinguishes tracking
  from cancellation or admission control.
