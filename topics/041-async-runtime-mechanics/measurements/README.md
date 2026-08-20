# Topic 41 measurement records

This visit records correctness, layout, and generated code. It reports no
timing. A manual single-threaded driver cannot measure a production executor,
channel, scheduler, or cancellation-latency path.

The required replication unit is one fresh process. Eight processes per host
must produce byte-identical output. Inner polls are state transitions.

Both required hosts passed the acceptance contract:

- [`2026-08-20-arm.md`](2026-08-20-arm.md)
- [`2026-08-20-xxl.md`](2026-08-20-xxl.md)
- [`2026-08-20-comparison.md`](2026-08-20-comparison.md)
- [`raw/2026-08-20-f03eb7c/`](raw/2026-08-20-f03eb7c/)
