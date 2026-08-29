# Topic 50 measurements

This directory separates checked measurement summaries from raw receipts.

The focused experiment measures process elapsed time, thread CPU time,
affinity and nice readback, context-switch counts, exact host metadata, and
linked code for one composite placement-and-priority comparison. It does not
measure production scheduling delay, isolate simultaneous multithreading
(SMT), or identify a unique scheduler mechanism.

One complete four-process block is one replication. The reported Student-t
interval covers between-block variation on one exact host, binary, workload,
placement, and run window. It does not cover other hosts, builds, kernels,
processor families, or workloads.

Raw archives, controller validation, source identity, and the runtime `xxl`
resolution belong under [`raw/`](raw/).
