# Topic 38 measurement contract

The preliminary summaries are:

- [`2026-08-17-arm.md`](2026-08-17-arm.md)
- [`2026-08-17-xxl.md`](2026-08-17-xxl.md)
- [`2026-08-17-comparison.md`](2026-08-17-comparison.md)

They must be replaced or promoted with exact-source receipts after the
checked-in source candidate runs on both required hosts. No preliminary raw
receipt is represented as repository evidence. See [`raw/README.md`](raw/README.md).

## Workload boundary

The C probe sends one generated 512 MiB immutable file through an IPv4 loopback
TCP socket. The file resides on memory-backed temporary storage and receives
one sequential warmup read before the fixed timing schedule. This makes a hot
page-cache workload likely; it does not prove that every page stayed resident.
The requested chunk is 256 KiB.

The three methods are:

- `buffered`: allocate a chunk buffer, loop over `pread`, and loop over `send`;
- `sendfile`: loop over `sendfile`; and
- `splice`: create a pipe, loop from file to pipe, then drain pipe to socket.

`transfer_sec` excludes socket construction and file open. It includes
buffered allocation and release and includes `splice` pipe creation and close.
These method-specific setup costs are intentionally part of the preserved
preliminary treatment. Because the boundary is asymmetric, an elapsed
difference cannot be attributed solely to avoided payload copies.

`setup_sec` records socket and file setup before that interval. `total_sec`
records the broader in-process interval. Sender CPU, receiver CPU, call counts,
socket buffers, pipe capacity, and shell-observed outer process time are
separate observations.

## Correctness and completion controls

Before timing, each method sends 16,777,219 bytes and the receiver checks every
byte against the deterministic source pattern. Timing still requires exact
received length, clean receiver status, clean transfer status, and successful
process exit, but omits the per-byte comparator.

The `MSG_ZEROCOPY` control is correctness-only. It enables `SO_ZEROCOPY` on an
IPv4 loopback TCP socket, sends eight page-aligned 64 KiB regions, retains the
entire 524,288-byte buffer, verifies receiver bytes, and processes the error
queue until inclusive completion ranges cover identifiers 0 through 7. It
records whether Linux reported copied fallback. It does not time this path or
test a network device.

## Replication and analysis

The fixed seed `38017` creates eight paired four-period blocks for each of
buffered-versus-`sendfile`, buffered-versus-`splice`, and buffered A/A. Each
block uses `ABBA` or `BAAB` order. There are 96 timing processes. One fresh
process is the treatment application; one complete four-period block is the
analysis unit. There is no retry and no result-driven stopping.

For each positive timing metric, analysis subtracts the block mean log time for
label A from the block mean log time for label B. Exponentiating the mean of
the eight contrasts produces the B/A geometric ratio. The report retains every
block contrast and the sample standard deviation of the eight log contrasts.
It also gives a marginal Student-t 95-percent working-model interval. Sequential
blocks on one shared host do not establish independence or normality. The
interval describes this run; it does not predict another run or correct for
multiple comparisons.

The A/A path runs buffered under both labels. It checks labels, schedule,
execution, parsing, and analysis. Eight blocks do not make it an equivalence
test, a calibrated noise floor, or a correction for the treatment ratios.

## Exact-source receipt requirements

A promoted result must retain:

- the full measured Git commit and source-archive SHA-256;
- the SSH alias, runtime-resolved hostname, architecture, kernel, CPU identity,
  available CPU count, affinity, page size, and relevant resource limits;
- Rust, Cargo, Python, C compiler, linker, and binary-utility versions;
- generic and native build flags, source hashes, executable hashes, and linked
  dynamic dependencies;
- all correctness, schedule, process, raw stream, contrast, summary,
  `MSG_ZEROCOPY`, generated-code, and validator receipts;
- a manifest over the result archive and a matching digest after retrieval; and
- exact runner and validator sources from the measured commit.

The host runner must use an extracted read-only snapshot of the committed
archive. The validator must reject missing rows, retries, schedule drift,
incorrect bytes, nonzero status, raw-output hash drift, incomplete blocks,
invalid analysis, missing completion coverage, or executable identity drift.

## Interpretation boundary

- **Measured:** exact byte counts, elapsed and CPU intervals, calls, pipe and
  socket sizes, completion records, order, host/tool metadata, hashes, and
  linked external call sites.
- **Derived:** paired log contrasts, geometric ratios, sample dispersion,
  descriptive intervals, and checked analytical cost models.
- **Inferred:** copy, cache, page-reference, protocol, scheduler, and device
  mechanisms unless separately isolated.
- **Not tested:** storage misses, NIC or DMA behavior, a remote receiver, TLS,
  congestion, concurrent load, slow-request tails, energy, or processor-family
  generality.
