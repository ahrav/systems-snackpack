# Topic 41 measurement records

This visit records correctness, layout, and generated code. It reports no
timing. A manual single-threaded driver cannot measure a production executor,
channel, scheduler, or cancellation-latency path.

The required replication unit is one fresh process. Eight processes per host
must produce byte-identical output. Inner polls are state transitions.

Host-specific notes and sealed exact-source receipts are added only after both
required hosts pass the acceptance contract in [`../rounds/01.md`](../rounds/01.md).
