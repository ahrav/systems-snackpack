# Two-host results, 2026-10-15

Crossbeam ArrayQueue wins all eight host/workload cells against this mutex deque
under the declared rule: every one of six paired ratios exceeds 1.05 in its favor.
These are saturated integer-job transfers with an outer yield on full/empty.
They do not establish a universal queue winner.

Measured source: `fc53924e10865e70e9c076c4a0ace48ac4d04131`. The measured runner is the `run.py`
(SHA-256 `5e15959f6b8aedce8b081d40b9b26ef1e9af9ca86be78dc638b5e8e5cb911174`) and `linux-run.sh`
(SHA-256 `4d5c09b63cbf2224d17c44efe1bbfe1afd10e26d308bcc920a79b0b05095011b`) at that commit.
The published runner differs after review: it refuses an existing output directory, verifies
SOURCE_COMMIT against HEAD and the tracked inputs, clears Cargo rustflags, profile and target
environment overrides, records the verbose build, honors `CARGO_TARGET_DIR`, searches every socket
for eight cores, rejects a row whose echoed configuration differs from its command, and publishes
`results.json` only after the summary is complete. The published library adds a checked
participant-count addition before the barriers. The timed loop, campaign commands, toolchain and
lockfile are unchanged; the retained `binary.sha256` files hash the measured commit's build.
Rust 1.93.1, LLVM 21.1.8,
Cargo release defaults, no target-cpu override, crossbeam-queue 0.3.12 and
crossbeam-utils 0.8.23. Both hosts use Amazon Linux 2023, kernel 6.12.110.

Arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, AArch64 ARM vendor/model 1/r1p1,
64 physical cores. The available lscpu output does not identify a commercial CPU model.
xxl: dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, verified x86_64,
Intel Xeon Platinum 8488C, 2 sockets, 48 cores/socket, 2 threads/core.
Both runs use CPUs 0 through 7, verified distinct physical cores on one socket.
Threads can migrate inside this mask. Host interference, frequency and sibling
activity are uncontrolled. Compare each queue within a host, not architectures.

Six paired independent process trials per cell alternate array/mutex order.
One warmup pair per cell is excluded: 48 measured and eight warmup processes per
host. Each producer sends 100,000 jobs. 1P/1C sends 100,000; 4P/4C sends 400,000.
Results below are nanoseconds of batch wall time divided by completed jobs,
not individual request latency. Intervals are observed min/max, not confidence
intervals. No separate A/A calibration was performed.

| Host | P/C | Capacity | Array median [min, max] ns/job | Mutex median [min, max] ns/job | Winner |
|---|---:|---:|---:|---:|---|
| arm | 1/1 | 4 | 131.5 [84.2, 148.2] | 212.5 [200.1, 245.6] | array |
| arm | 1/1 | 1024 | 35.9 [32.6, 38.4] | 202.2 [136.3, 360.6] | array |
| arm | 4/4 | 4 | 156.5 [131.4, 211.0] | 507.1 [476.5, 563.6] | array |
| arm | 4/4 | 1024 | 138.4 [71.2, 199.8] | 301.5 [269.2, 348.6] | array |
| xxl | 1/1 | 4 | 102.3 [83.3, 115.2] | 212.7 [166.1, 277.0] | array |
| xxl | 1/1 | 1024 | 24.6 [21.3, 26.9] | 263.5 [216.7, 324.5] | array |
| xxl | 4/4 | 4 | 217.7 [188.0, 260.2] | 897.6 [739.7, 1002.3] | array |
| xxl | 4/4 | 1024 | 148.8 [121.8, 214.7] | 336.2 [327.8, 361.3] | array |

Timing includes start-barrier release, scheduling, queue calls, consumer buffer
writes and joins. Thread creation and buffer allocation precede timing; sorting
and exact-ID verification follow timing. Both queue wrappers use enum dispatch;
the array queue is boxed. The mutex implementation enforces a logical bound.
Its lock can block while ArrayQueue retries internally. Outer retry counts omit
these internal events and must not be interpreted as total contention.

Every run checks exact delivery. On both hosts the model, six unit tests, one
doctest, Clippy and release build passed. Sequential oracles and stress do not
prove every concurrent history, weak-memory behavior, fairness, wait-freedom,
payload destruction or machine-counter wrap.

The larger capacity plausibly amortizes full/empty handoffs in 1P/1C, but no
mechanism counters were collected. The data establish timing differences for
these wrappers and this workload; attribution to cache coherence or instruction
sets remains inference. Parking channels, SPSC queues and real job service time
were not measured. Retain those options when their contracts fit better.

Replay from the root of a git checkout at SOURCE_COMMIT with a new output path:

```sh
bash topics/078-bounded-mpmc-queue/linux-run.sh results SOURCE_COMMIT
```

The source archive SHA-256 is recorded in `source-identity.json`; its 261 paths
include all workspace manifests and Rust targets needed by Cargo metadata plus
this topic's exact files. The retained archive excludes unrelated historical
measurement payloads. Each remote verified the archive before extraction.
