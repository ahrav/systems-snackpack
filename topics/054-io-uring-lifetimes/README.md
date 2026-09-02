# `io_uring` ownership and completion lifetimes

`io_uring` cancellation creates another operation. It does not erase the
target. The cancel request and target each produce a completion queue entry
(CQE), and their order is not a correctness signal. Keep the target state and
payload alive until the target's terminal CQE arrives. A replaced registered
resource also needs its retirement CQE.

This crate turns that rule into a small lifecycle model. The native Linux probe
checks baseline setup, `SINGLE_ISSUER` ownership enforcement,
`DEFER_TASKRUN` progress, and async-cancel completion correlation.

## Queue roles

A submission queue entry (SQE) stages one request. The kernel can reuse that SQ
slot after consuming it while the operation remains in flight. The CQ holds
results that userspace has not consumed. SQ capacity, in-flight admission, and
CQ capacity are separate bounds.

One dedicated owner gives a direct submission proof. Workers can send logical
requests to that owner through channels. `SINGLE_ISSUER` constrains one ring,
not the whole process.

`DEFER_TASKRUN` requires `SINGLE_ISSUER`. The owner must enter with
`IORING_ENTER_GETEVENTS` within a bounded interval. Peeking at the CQ does not
guarantee progress.

## Cancellation ledger

The model separates three obligations:

1. the target terminal CQE;
2. the cancel request's CQE, when cancellation was submitted;
3. the resource-retirement CQE, when a registered resource was replaced.

The target payload becomes reclaimable after obligations 1 and 3. The whole
ledger entry retires after all applicable obligations arrive.

The ledger is not cloneable or copyable. One owner consumes each completion
obligation once. For a multishot target, a CQE with `IORING_CQE_F_MORE` leaves
the target obligation outstanding. Only a CQE without that flag is terminal.
Resource tag zero disables kernel tagging, so the model accepts only nonzero
retirement tags.

Operation tokens and retirement tags both arrive through CQE `user_data`.
Reserve disjoint namespaces for them in the runtime dispatcher. The model uses
typed observation methods after dispatch and cannot infer that namespace split.

The model also assumes each target and cancel SQE will emit the CQE it records.
Do not set `IOSQE_CQE_SKIP_SUCCESS` when a successful completion would satisfy
one of these obligations. A skipped success would leave the ledger waiting for
a CQE that Linux intentionally omitted.

Use a generation-qualified `user_data` token. Reusing a raw slot lets a stale
CQE match a new request. Closing the application file descriptor or dropping a
future does not replace the terminal-CQE proof.

## Checked cost bounds

The completion-visibility model adds operation service time, the longest owner
`GETEVENTS` gap, and CQ drain time. With 200 microseconds of service, a
500-microsecond owner gap, and 50 microseconds to drain, the bound is 750
microseconds.

The CQ model multiplies burst CQEs per second by the longest drain interval,
then adds completion fan-out and a safety margin. It also rounds the requested
SQ size and never returns a smaller CQ. With a 128-entry SQ, 50,000 CQEs per
second, a 2,000-microsecond drain interval, 24 extra CQEs, and a margin of 32,
the raw completion bound is 156. The next power-of-two CQ size is 256.

Run the executable model:

```bash
cargo run -p io-uring-lifetimes --example lifecycle_costs
```

Run the focused tests:

```bash
cargo test -p io-uring-lifetimes
```

The Rust model does not call Linux. See [the experiment](experiment/README.md)
for the exact native probe and [the sources](references.md) for versioned
contracts.
