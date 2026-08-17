# Topic 38 measurement contract

The retained summaries are:

- [`2026-08-17-arm.md`](2026-08-17-arm.md)
- [`2026-08-17-xxl.md`](2026-08-17-xxl.md)
- [`2026-08-17-comparison.md`](2026-08-17-comparison.md)

Both hosts ran measured source commit
`c6b76b4429272814c7e3ab57a199c9d2c2d8ce66` from the same source archive,
SHA-256
`f6e75b525d82964437d23f74494758ccdddd1bc0da31e3b2971cdf4d9cd913e4`.
The later evidence-only commit does not change the measured experiment source.
See [`raw/README.md`](raw/README.md) for the retrieved archives and their
integrity contract.

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

`transfer_sec` starts after file open and sender socket connect. It includes
buffered allocation and release and includes `splice` pipe creation and close.
There is no receiver-ready barrier, so receiver `accept` and buffer allocation
can overlap the beginning. The interval ends after sender shutdown, receiver
report collection, and child exit. These method-specific costs and
endpoint-lifetime costs are intentionally part of the retained treatment.
Because the boundary is asymmetric, an elapsed difference cannot be attributed
solely to avoided payload copies. Sender CPU covers this interval; receiver CPU
covers the child's whole lifetime.

`setup_sec` records socket and file setup before that interval. `total_sec`
records the broader in-process interval. Sender CPU, receiver CPU, completed
non-`EINTR` operation counts, socket buffers, pipe capacity, and shell-observed
outer process time are separate observations.

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

For `transfer_sec` and `setup_sec`, analysis subtracts the block mean log time
for label A from the block mean log time for label B. Exponentiating the mean
of the eight contrasts produces the B/A geometric ratio. The report retains
every block contrast and the sample standard deviation of the eight log
contrasts. It also gives a marginal Student-t 95-percent working-model interval.
Sender CPU, receiver CPU, total time, and outer process time receive descriptive
A/B medians but no paired ratio or interval. Sequential blocks on one shared
host do not establish independence or normality. The interval describes this
run; it does not predict another run or correct for multiple comparisons.

The A/A path runs buffered under both labels. It checks labels, schedule,
execution, parsing, and analysis. Eight blocks do not make it an equivalence
test, a calibrated noise floor, or a correction for the treatment ratios.

## Exact-source retained receipts

The retained result includes:

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

The host runner verified the source-archive digest before extraction, verified
that its invoked runner matched the archived runner, and recorded byte-identical
source manifests before and after each run. Each source manifest listed 1,773
entries and had SHA-256 digest
`0b2ceed67acaf154b8aaf1bbf75d05f629c1b39d279dc003555cc3690b222688`.
The validator rejects missing rows, retries, schedule drift, incorrect bytes,
nonzero status, raw-output hash drift, incomplete blocks, analysis values that
do not exactly match a fresh recomputation, missing completion coverage,
inconsistent `ee_code` and copied-fallback fields, or executable identity drift.

Both host summaries and validators report `PASS`. Each host contributed 96
successful timing processes, three exact-byte correctness processes, complete
buffered A/A coverage, and generic and native `MSG_ZEROCOPY` completion
coverage of 8/8 with copied fallback on loopback. After retrieval, the two
result archive digests matched `raw/2026-08-17-c6b76b4/SHA256SUMS`; all 272
entries in each archive's internal manifest also verified.

Strict generated-code receipts contain exactly five transfer call sites and
three completion-control call sites for each generic and native executable on
each host. They establish executable structure, not the executed kernel path.

## Interpretation boundary

- **Measured:** exact byte counts, elapsed and CPU intervals, completed
  non-`EINTR` operation counts, pipe and socket sizes, completion records,
  order, host/tool metadata, hashes, and linked external call sites.
- **Derived:** paired log contrasts, geometric ratios, sample dispersion,
  descriptive intervals, and checked analytical cost models.
- **Inferred:** copy, cache, page-reference, protocol, scheduler, and device
  mechanisms unless separately isolated.
- **Not tested:** storage misses, NIC or DMA behavior, a remote receiver, TLS,
  congestion, concurrent load, slow-request tails, energy, or processor-family
  generality.
