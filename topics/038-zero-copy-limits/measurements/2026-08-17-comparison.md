# Preliminary cross-host comparison

Status: preliminary scratch evidence. Both hosts ran source bytes with the same
transfer-source SHA-256, but the run predates the committed artifact. Exact
checked-in source receipts must replace or promote these observations.

## What was measured

Both required targets sent the same 512 MiB prewarmed memory-backed file over
IPv4 loopback TCP. Each method used 256 KiB requested chunks. Eight paired,
order-balanced complete blocks per pair supplied the process-level replication.
All 96 timing processes and three separate exact-byte correctness processes per
host passed.

| Pair; candidate / buffered elapsed | Arm target | `xxl` resolved x86-64 target |
| --- | ---: | ---: |
| `sendfile` / buffered | 0.551930 [0.542973, 0.561035] | 0.752378 [0.735321, 0.769831] |
| `splice` / buffered | 0.558441 [0.548789, 0.568263] | 0.749593 [0.745887, 0.753316] |
| buffered B / buffered A | 1.003497 [0.995345, 1.011716] | 0.997731 [0.979570, 1.016229] |

Brackets contain marginal Student-t 95-percent working-model intervals over
eight complete-block log contrasts. They cover variation among the sequential
process blocks in this run, under assumptions the run does not prove. They do
not cover future runs, machines, workloads, or processor families.

Both hosts showed lower elapsed time and lower sender CPU for `sendfile` and
`splice` than for buffered I/O inside this treatment. Both also showed more
receiver CPU for the copy-avoiding paths. The size of the ratios differed by
host. These are measured observations. Attributing them to a specific copy,
cache, protocol, or scheduler mechanism is an inference not isolated here.

The `transfer_sec` interval includes application-buffer allocation/free for
buffered and pipe create/close for `splice`. That preserved asymmetry means the
ratios compare complete declared treatments, not only byte-copy work.

## What cannot be compared

The named hosts are two convenient cases, not samples of Arm and x86-64
families. Do not subtract their ratios or treat the difference as an
instruction-set effect. Host firmware, virtualization, CPU model, kernel,
toolchain, socket path, scheduler, and neighboring work differ together.

The loopback `MSG_ZEROCOPY` controls on both hosts verified buffer lifetime and
all bytes, and both observed copied fallback. They intentionally provide no
performance comparison.

The run excludes physical storage, network devices, DMA, remote receivers,
TLS, congestion, application transformations, concurrency, memory pressure,
energy, and slow-request tails. Each requires a separate experiment with its
own correctness and ownership contract.
