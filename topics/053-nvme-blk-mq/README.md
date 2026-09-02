# NVMe and the Linux block input/output path

Fast storage moves the bottleneck from media toward queue management,
interrupts, software scheduling, and offered concurrency. NVMe exposes
submission and completion queues. Linux `blk-mq` maps per-CPU software staging
onto one or more hardware dispatch contexts. The two queueing systems are
related, but they are not the same object and they do not have to map one to
one.

This crate keeps the useful capacity and CPU-cost arithmetic executable. The
Linux experiment measures one-thread native asynchronous direct reads at queue
depth one and eight on the required Arm and x86-64 hosts. It does not store the
full lesson transcript.

## The path to keep in mind

For a direct regular-file read, a useful simplified path is:

```text
application
  -> read API and filesystem mapping
  -> bio construction and merging or splitting
  -> blk-mq software context
  -> blk-mq hardware context and driver tags
  -> NVMe submission queue and doorbell
  -> controller or virtual storage backend
  -> NVMe completion queue and interrupt or polling
  -> blk-mq completion
  -> filesystem and application completion
```

A page-cache hit can stop above the block layer. `O_DIRECT` reduces page-cache
participation, but it does not bypass the filesystem, hypervisor, provider
backend, controller cache, or device-internal cache.

## Two different queue models

An NVMe submission queue is a circular host-memory array of commands. Software
writes commands, advances the tail doorbell, and later consumes entries from a
completion queue. Each completion identifies its command by submission queue
identifier and command identifier. A phase tag distinguishes a new completion
from an old value in a reused completion slot. Multiple submission queues may
share one completion queue.

Linux `blk-mq` first stages requests in per-CPU software contexts. It maps them
to hardware contexts used for dispatch to a driver. A scheduler may order work
between those layers. Scheduler tags and driver tags therefore describe
different admission points. A hardware-context directory in sysfs is evidence
of exported driver topology, not proof that one experiment used every queue or
that each context maps to one NVMe submission queue.

## Technique comparison

| Technique | Useful when | Main benefit | Main cost or limit |
|---|---|---|---|
| Synchronous depth one | Latency matters more than throughput, or dependencies are serial | Simple attribution and low offered queueing | Cannot hide service time |
| Asynchronous queue depth greater than one | Independent operations can overlap | Hides service time and can approach a throughput cap | More queueing, buffers, tags, and completion work |
| Interrupt completion | Arrival rate is moderate or cores cannot busy-wait | CPU can do other work | Interrupt and scheduling overhead, possible coalescing delay |
| Polling | Tail latency justifies a dedicated CPU budget | Avoids interrupt wakeup on the chosen path | Burns CPU and can contend with the producer or device |
| No elevator | Fast multiqueue device already handles ordering well | Avoids scheduler work | Gives up host-side prioritization and merging opportunities |
| Multiqueue scheduler | Fairness, class control, or locality needs host policy | Central policy above driver queues | Extra locks, bookkeeping, and possible dispatch delay |

## Checked planning models

The effective offered depth is bounded by every admission point:

```text
D_effective = min(D_app, Q_active * T_queue, D_device)
```

For application depth 512, eight active queues, 64 usable slots per queue, and
a device limit of 128, the effective depth is `min(512, 8 * 64, 128) = 128`.
The formula is a capacity bound. It does not prove occupancy.

Little's Law gives a first throughput bound:

```text
IOPS_concurrency = D_effective / L_service
IOPS = min(IOPS_concurrency, IOPS_device_cap)
```

With depth 128 and mean service time 500 microseconds,
`128 / 0.0005 s = 256,000 IOPS`. A 200,000 IOPS device or provider cap makes
the result 200,000 IOPS. At 4 KiB per operation, bandwidth is
`200,000 * 4096 = 819,200,000 bytes/s`, or 781.25 MiB/s.

Batching changes fixed CPU cost per operation:

```text
C_per_io = C_variable + (C_submit_fixed + C_complete_fixed) / B
cores = IOPS * C_per_io / usable_cycles_per_core_second
```

For 500 variable cycles, 800 submission cycles, 480 completion cycles, and a
batch of 32, cost is `500 + (800 + 480) / 32 = 540 cycles/IO`. At 200,000 IOPS
and 2.5 billion usable cycles per core-second, the model requires
`200000 * 540 / 2500000000 = 0.0432` core. These are planning substitutions, not
measurements from the two hosts.

Run all checked substitutions with:

```bash
cargo run -p nvme-blk-mq --example nvme_costs
```

## Focused Linux experiment

The native probe creates and verifies a private, deterministic regular file.
Each timed process uses one userspace thread and raw Linux asynchronous I/O
syscalls with `O_DIRECT`. It compares 4 KiB random reads at depth one and depth
eight. Separate fresh processes follow balanced `ABBA` and `BAAB` blocks. An
identical depth-one A/A comparison tests whether label and order noise can
explain a small result.

The receipt binds the exact Git archive, source and binary digests, host,
kernel, compiler, filesystem, mount, block stack, NVMe sysfs, blk-mq topology,
per-process storage counters, generated assembly, and every retained result.
Full receipts stay outside Git. Only compact host records and a manifest of the
sealed external bundle belong here.

See [the experiment contract](experiment/README.md), [measurement
records](measurements/README.md), and [primary references](references.md).

## Evidence boundary

The measured unit is one fresh process, not one inner read. A requested depth
is an application upper bound, not proof of queue occupancy. Linux native AIO
completion is not an NVMe completion entry. Filesystem mapping, splitting,
merging, virtualization, ambient device traffic, and provider controls can all
separate the two.

The required hosts expose devices named `nvme0n1`, but their model is Amazon
Elastic Block Store. That is evidence for the guest-visible NVMe and blk-mq
path. It is not evidence for local flash. Device-wide counters may contain
unrelated traffic, and `read_ms / completed_reads` includes block-layer
queueing rather than only media service.

The experiment does not isolate architecture effects, prove a one-to-one
queue mapping, measure persistence, or attribute time among filesystem,
blk-mq, driver, hypervisor, provider backend, controller, and media.

## Failure checklist

- Depth can stop at application limits, scheduler tags, driver tags, controller
  capacity, provider caps, or dependencies between operations.
- A saturated queue raises residence time even when throughput no longer rises.
- One hot CPU or one shared hardware context can bottleneck before the device.
- Interrupt coalescing saves CPU but can add completion delay.
- Polling can improve a selected tail while wasting or stealing CPU.
- A queue timeout leaves an uncertain operation until the completion and retry
  contract is understood.
- A reset can abort commands, reorder recovery work, and expose stale command
  identifiers if generation handling is wrong.
- A guest NVMe name does not prove local media or a dedicated backend.
- A scheduler choice that wins one workload can hurt fairness or mixed traffic.
- Increasing depth without an A/A control can turn host noise into a mechanism
  claim.

## Practical rule

Start with the completion promise and the slowest credible layer. Offer only
enough independent work to hide its service time and reach the required rate.
Check every queue and tag bound on the path. Then measure whole fresh processes
with storage counters and an A/A control. Increase depth only while useful
throughput rises within the latency, memory, fairness, and CPU budget.
