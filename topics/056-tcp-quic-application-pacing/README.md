# TCP and QUIC application pacing

An overdue schedule can release a burst after a CPU pause. Capped byte credit
bounds admission even when the application wakes late. The example compares
100 chunks of 1,200 bytes at 12 MB/s, with and without a five-millisecond pause.

```bash
cargo test -p tcp-quic-application-pacing
cargo run -p tcp-quic-application-pacing --example pacing
```

The library couples admission to one nonblocking writer. It charges only the
accepted prefix, retains fractional byte credit, preserves credit on
`WouldBlock`, and rejects clock regression before calling the writer. A stream
buffer larger than capacity is offered in prefixes. This API cannot be used
unchanged for an indivisible datagram larger than capacity.

The experiment is a deterministic admission model. Its microsecond outputs
are simulated times, not elapsed-time measurements. No TCP or QUIC stack,
network path, loss recovery, wire departure, or architecture speedup is tested.
The byte envelope is `admitted <= capacity + rate * elapsed` at the admission
boundary. Pending producer data needs an independent limit.

The time bound uses caller-supplied admission-check timestamps. Preemption
between a clock check and writer execution can change actual acceptance spacing.
The API does not make those operations atomic or implement a kernel pacer.

## Controls and selection

| Control | Boundary | Failure to avoid |
| --- | --- | --- |
| Application bucket | Bytes accepted downstream | Excess pause credit or an unbounded producer queue |
| Receiver flow control | Permitted new data | Late credit updates or exhausted connection/stream credit |
| Congestion control | Path load and outstanding traffic | Treating a fixed application quota as path feedback |
| Transport pacing | Eligible packet scheduling | Assuming write completion proves packet departure |

Use transport pacing for congestion-responsive packet timing. Use an
application bucket for a quota with a burst cap. On Linux, inspect the active
`fq`/TCP pacing path before interpreting `SO_MAX_PACING_RATE`. `TCP_NODELAY`
does not override flow control, congestion control, or pacing.

See [round 01](rounds/01.md) for the cost model and evidence boundaries, and
[primary references](references.md) for the transport and Linux contracts.
