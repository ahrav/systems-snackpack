# Primary references

## Logical and causal order

- Leslie Lamport, [*Time, Clocks, and the Ordering of Events in a Distributed
  System*](https://lamport.azurewebsites.net/pubs/time-clocks.pdf), defines
  happens-before, the scalar clock condition, and the process-identity extension
  to a total comparator. The comparator assumes an event set; it does not supply
  agreement or delivery finality.
- Colin Fidge, [*Timestamps in Message-Passing Systems That Preserve the Partial
  Ordering*](https://ics.uci.edu/~cs230/reading/1.pdf), defines timestamp arrays
  that retain the partial order and expose concurrent event pairs.
- Nuno Preguiça et al., [*Dotted Version
  Vectors*](https://arxiv.org/abs/1011.5808), separates one update's dot from its
  causal past for per-key optimistic replication. This artifact implements only
  a fixed two-component event vector, not a version-vector store.
- Sandeep Kulkarni et al., [*Logical Physical
  Clocks*](https://cse.buffalo.edu/~demirbas/publications/hlc.pdf), specifies the
  two-field HLC transition used by the probe. Its physical-affinity bounds depend
  on the paper's clock-error assumptions.
- Diego Ongaro and John Ousterhout, [*In Search of an Understandable Consensus
  Algorithm*](https://raft.github.io/raft.pdf), defines committed replicated-log
  order. It marks the boundary between sortable timestamps and protocol
  agreement; the artifact implements no consensus.

## Physical time and uncertainty

- Linux [`clock_gettime(2)`](https://man7.org/linux/man-pages/man2/clock_gettime.2.html)
  distinguishes settable real time, frequency-adjusted monotonic time, raw time,
  and suspend-inclusive boot time.
- [RFC 5905](https://www.rfc-editor.org/rfc/rfc5905.html) specifies Network Time
  Protocol version 4 offset, delay, dispersion, and clock-discipline behavior.
- [RFC 8915](https://www.rfc-editor.org/rfc/rfc8915.html) specifies Network Time
  Security and retains the asymmetric-delay attack boundary.
- Linux [PTP hardware-clock
  documentation](https://docs.kernel.org/driver-api/ptp.html) defines the dynamic
  clock interface for Precision Time Protocol hardware clocks.
- James Corbett et al., [*Spanner: Google's Globally-Distributed
  Database*](https://research.google.com/archive/spanner-osdi2012.pdf), defines
  the TrueTime interval and commit-wait protocol. Its historical uncertainty and
  latency measurements are not constants for current systems.
- Rust [`SystemTime`](https://doc.rust-lang.org/stable/std/time/struct.SystemTime.html)
  documents non-monotonic wall time. Rust
  [`Instant`](https://doc.rust-lang.org/stable/std/time/struct.Instant.html)
  documents the portable local elapsed-time abstraction and its platform
  boundary.

## Artifact boundary

The sources justify algorithm contracts and failure boundaries. They do not
validate this implementation. Unit tests, fresh-process receipts, and source and
binary hashes validate the checked-in artifact within its declared scope. The
retained two-host generated-code records describe superseded commit `b9bb526`
and a non-pinned toolchain (see `measurements/README.md`); they do not validate
the current artifact until regenerated for the final exact source.
