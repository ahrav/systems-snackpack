# Async runtime mechanics

An async task is a stored state machine, not a function that the runtime can
interrupt anywhere. Its suspended values consume memory. Its current `poll`
must return before another task can run on that worker. Dropping it preserves
Rust memory safety but can lose application progress.

The running example races receives from two parcel queues. A losing receive is
safe to cancel only when the parcel remains queued or has moved into an owner
that survives the dropped future.

## Three separate contracts

Calling an `async fn` creates an inert `Future`. The executor starts work by
calling `Future::poll` with a `Context` and pinned access to the future.

- `Poll::Ready(value)` completes the operation.
- `Poll::Pending` suspends it after the future arranges a later wake.
- A `Waker` reports possible progress. Wake calls can coalesce; they are not an
  event count.
- `Pin` prevents movement that could invalidate a polled future's internal
  references. Pinning does not require a heap allocation or one operating-system
  thread.

An `.await` suspends only when its child returns `Pending`. An always-ready child
can let the parent continue in the same poll.

## Suspended values set the frame size

The compiler uses an enum-like state per suspension point. The exact layout is
not a stable application binary interface (ABI). This screen identifies the
load-bearing values:

```text
future bytes ~= align(tag and fixed captures + widest live suspended state)
```

A 4,096-byte array used after `.await` remains in the future. Finishing with it
before `.await` can leave only its small result. `size_of_val` measures the exact
compiler result; the screen explains which source changes to test.

For `N` resident runtime tasks:

```text
resident bytes ~= N * (runtime overhead + max(future, output) + allocator overhead)
                 + shared queue storage
```

Tokio 1.53.1 stores the future and completed output in overlapping task-stage
storage. Its header, scheduler state, ownership links, and join state add
version-specific overhead. Measure the runtime version instead of treating the
future size as the whole task size.

`future_frame_screen` and `task_residency_screen` implement checked versions
of these two arithmetic screens.

## A poll is a cooperative scheduling unit

The runtime cannot preempt synchronous work inside `poll`. A cancellation
request completes no sooner than the current poll returns, the task is scheduled
to observe it, and synchronous destructors finish:

```text
cancellation floor = remaining poll + scheduling delay + synchronous drop work
```

`cancellation_latency_floor` performs the checked sum. The model supplies a
lower bound only. A finite upper bound requires bounded poll time, task count,
scheduler availability, and cleanup.

## Concurrency choices preserve different ownership

| Choice | Use it for | Operational catch |
| --- | --- | --- |
| Sequential `.await` | Dependent work | Independent latency does not overlap |
| `join!` | A fixed set that must all finish | Branches share one task; one blocking poll stalls all |
| `try_join!` | Fail-fast inline work | It drops unfinished siblings, which must be safe to cancel |
| `select!` | A race with a defined loser state | It drops directly owned losing futures |
| `spawn` plus `JoinHandle` | Independent scheduling or parallel execution | Dropping the handle detaches the task |
| `JoinSet` | Dynamically owned spawned children | Abort still needs a completion drain |
| Cancellation token plus completion tracker | Graceful shutdown | Signaling, admission, joining, and failure collection remain separate |
| Blocking pool | Finite blocking calls | Started blocking work cannot be aborted |

Randomized first polling in `select!` is not a starvation guarantee. An explicit
biased order transfers fairness responsibility to the caller.

## Cancellation safety is a protocol property

The example contains two hand-written receive futures:

```text
unsafe: queued -> staged inside future -> Pending -> drop -> lost
safe:   queued -> Pending -> drop -> still queued
```

Memory remains safe in both paths. Only the second preserves the parcel
invariant. Other sound designs keep ownership outside the cancelable future,
roll back synchronously with a guard, checkpoint an idempotent operation, or
move the work into an owned child and join it.

Stable Rust 1.97.1 has no stable async destructor. Network flushes, protocol
close handshakes, and durable commits need an explicit async shutdown phase
before task return.

A structured shutdown proves four facts:

1. admission stopped;
2. current children received a stop signal;
3. the owner joined or tracked them through cleanup;
4. the owner collected or classified every failure.

No single Tokio type supplies all four.

## Failure checks

- Calling an async function does not start it.
- `.await` does not guarantee a yield.
- One wake does not imply one poll.
- Pinning does not imply boxing.
- Dropping `JoinHandle` detaches instead of cancelling.
- Abort requests cancellation; it does not prove completion.
- `select!` can discard hidden input/output progress or wait-queue position.
- Closing `TaskTracker` does not reject new tasks.
- Started `spawn_blocking` work cannot be aborted.

## Focused experiment

[`examples/state_and_cancellation.rs`](examples/state_and_cancellation.rs)
compares equal 4 KiB work placed before and across a suspension. It also drops
the losing future in unsafe and safe two-queue races.

```bash
cargo run -p async-runtime-mechanics --example state-and-cancellation --release

# On a Linux target, after copying this Git-created archive and the matching
# committed runner into the current directory:
SSH_TARGET_LABEL=xxl \
SSH_RESOLVED_HOSTNAME="$(hostname -f)" \
./run_host.sh /tmp/topic41-results \
  "$SOURCE_COMMIT" "$SOURCE_ARCHIVE_SHA256" "$SOURCE_ARCHIVE"
```

The host runner records the source digest, host and compiler identity, target
features, eight fresh process outputs, Mid-level Intermediate Representation
(MIR), assembly, object code, symbols, and disassembly. It takes no timing. The
probe tests frame storage and one cancellation boundary, not a production
executor, channel, or scheduler.

See [`rounds/01.md`](rounds/01.md) for the acceptance contract and
[`measurements/`](measurements/) for retained evidence.

## Selection rule

Inspect live-across-await values before optimizing poll instructions. Identify
the ownership transfer before placing an operation in `select!`. Bound the
longest poll before promising shutdown latency. Keep spawned children owned
until their results and cleanup are observed.

Primary sources and version boundaries are in [`references.md`](references.md).
