# Primary references

## Queueing model and workload

- [Little, *A Proof for the Queuing Formula: L = lambda
  W*](https://doi.org/10.1287/opre.9.3.383) proves a relationship among
  long-run mean population, arrival rate, and time in system under the paper's
  conditions. It does not derive percentiles, select a queue bound, or require
  a finite-horizon sample to satisfy the identity exactly.
- [Kingman, *The single server queue in heavy
  traffic*](https://doi.org/10.1017/S0305004100036094) gives the single-server
  heavy-traffic basis for relating waiting to utilization and arrival/service
  variability. It motivates the fixed-versus-variable treatment; its
  asymptotic, unbounded-queue result is not used as an exact prediction for
  this finite queue with rejection.
- [Schroeder, Wierman, and Harchol-Balter, *Open Versus Closed: A Cautionary
  Tale*](https://www.usenix.org/conference/nsdi-06/open-versus-closed-cautionary-tale)
  distinguishes externally imposed arrivals from completion-paced clients and
  shows why the models can produce materially different response-time results.
  It motivates an open generator; it does not validate this generator's
  schedule fidelity, which must be checked from intended and actual timestamps.

## Rust implementation contracts

- [Rust `std::sync::mpsc::sync_channel`](https://doc.rust-lang.org/std/sync/mpsc/fn.sync_channel.html)
  defines a bounded FIFO channel with one receiver and a buffer size selected
  by `bound`. The probe uses bound `4` as waiting capacity; the worker's current
  job is outside that buffer.
- [Rust `SyncSender::try_send`](https://doc.rust-lang.org/std/sync/mpsc/struct.SyncSender.html#method.try_send)
  defines immediate success or a `Full`/`Disconnected` error. This is the
  admission mechanism that turns a full waiting buffer into a recorded
  rejection instead of blocking the open generator.
- [Rust `std::time::Instant`](https://doc.rust-lang.org/std/time/struct.Instant.html)
  provides monotonically nondecreasing opaque timestamps, but does not promise
  a steady clock and documents platform-specific behavior. The experiment
  therefore retains raw timestamps and exact host/toolchain provenance rather
  than treating nanosecond units as guaranteed timer resolution or cross-host
  equivalence.
