# Retained cross-host comparison

Status: retained evidence; both host runs, validators, retrieved archive
digests, and internal manifests passed.

Both hosts ran source commit
`c6b76b4429272814c7e3ab57a199c9d2c2d8ce66` from the same source archive,
SHA-256
`f6e75b525d82964437d23f74494758ccdddd1bc0da31e3b2971cdf4d9cd913e4`.
The retained Arm archive has SHA-256
`dcea29d8131846a50fd1f3da3a9efa618a0a0068d953bfd4734b9f159a494877`;
the retained `xxl` archive has SHA-256
`7403a907c3dd5f882b7dc77bdd8b977ef2571b784db3cd830a0fcff60592d995`.
A later evidence-only commit retains those artifacts and this prose without
changing the measured experiment source.

## What was measured

Both required targets sent the same 512 MiB prewarmed memory-backed file over
IPv4 loopback TCP. Each method used 256 KiB requested chunks. Eight paired,
order-balanced complete blocks per pair supplied the process-level replication.
All 96 timing processes and three separate exact-byte correctness processes per
host passed.

| Pair; B / A elapsed | Arm target | `xxl` resolved x86-64 target |
| --- | ---: | ---: |
| buffered A; `sendfile` B | 0.535180981 [0.528409683, 0.542039049] | 0.682472664 [0.668834195, 0.696389240] |
| buffered A; `splice` B | 0.538883052 [0.536157533, 0.541622426] | 0.676646220 [0.669328562, 0.684043880] |
| buffered A; buffered B | 1.000467926 [0.996529935, 1.004421478] | 0.994674852 [0.989507348, 0.999869343] |

Brackets contain marginal Student-t 95-percent working-model intervals over
eight complete-block log contrasts. They cover variation among the sequential
process blocks in this run, under assumptions the run does not prove. They do
not cover future runs, machines, workloads, or processor families.

The exact sample standard deviations of the eight log contrasts were:

| Pair | Arm target | `xxl` target |
| --- | ---: | ---: |
| buffered / `sendfile` | 0.015228149 | 0.024141832 |
| buffered / `splice` | 0.006064140 | 0.013004189 |
| buffered A / buffered B | 0.004716735 | 0.006229370 |

These ratios, intervals, and dispersion values are derived summaries. The host
notes retain the exact elapsed and central processing unit (CPU) medians from
each `summary.tsv`; CPU medians have no paired intervals.

The Arm A/A interval includes 1. The `xxl` A/A interval narrowly excludes 1
under the working model. It exposes a small residual label, order, or run
asymmetry and is not a calibrated noise correction. The candidate effects are
much larger, but the experiment still does not isolate payload-copy removal as
their cause.

On both named hosts, the `sendfile` and `splice` process observations had lower
elapsed and sender CPU medians than their paired buffered labels. Their
receiver CPU medians were higher. The ratios differed between the two hosts.
Attributing any difference to a specific copy, cache, page-reference, protocol,
or scheduler mechanism remains an inference because this experiment did not
isolate those mechanisms.

The `transfer_sec` interval includes application-buffer allocation/free for
buffered and pipe create/close for `splice`. That preserved asymmetry means the
ratios compare complete declared treatments, not only byte-copy work.

## What cannot be compared

The named hosts are two convenient cases, not samples of Arm and x86-64
families. Do not subtract their ratios or treat the difference as an
instruction-set architecture (ISA) effect. Host firmware, virtualization, CPU
model, kernel, toolchain, socket path, scheduler, and neighboring work differ
together.

The generic and native loopback `MSG_ZEROCOPY` controls on both hosts verified
all 524,288 bytes, held the aligned buffer until identifiers 0 through 7 were
complete, and observed `ee_code=1` copied fallback. Arm generic and native and
`xxl` generic used ranges `[0,0]`, `[1,7]`; `xxl` native used `[0,2]`, `[3,7]`.
These were correctness and lifetime controls only; they provide no performance
comparison or network-interface evidence.

Each host's generic and native generated-code receipts contain exactly five
transfer call sites and three completion-control call sites. Both validators
recomputed the analyses exactly and checked `ee_code` against the reported
copied-fallback state. Before and after source manifests each listed 1,773
entries and shared SHA-256
`0b2ceed67acaf154b8aaf1bbf75d05f629c1b39d279dc003555cc3690b222688`.

Raw measured evidence consists of exact byte counts, completed non-`EINTR`
operation counts, process elapsed and CPU intervals, completion records, host
and toolchain metadata, hashes, and linked call sites. Ratios, medians,
dispersion, and confidence intervals are derived. Copy and runtime-mechanism
explanations are inferred.

The run excludes physical storage, network interface cards, direct memory
access (DMA), remote receivers, Transport Layer Security (TLS), congestion,
application transformations, concurrency, memory pressure, energy, and
slow-request tails. Each requires a separate experiment with its own
correctness and ownership contract.
