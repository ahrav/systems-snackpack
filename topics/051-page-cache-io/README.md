# Linux page-cache I/O

Linux can turn file memory into a hidden performance and durability contract.
Buffered reads can reuse memory and fetch ahead. Buffered writes can return
before storage is durable. Direct I/O can bypass the page cache, but it also
removes automatic reuse and read-ahead from the data path.

This crate keeps the decision arithmetic executable. The native experiment
tests the matching Linux behavior on one Arm host and one x86-64 host. It does
not store the full lesson transcript.

## One file, four stages

Use an archive service as the running example. The service keeps a 4 GiB index
hot, scans an 8 GiB archive once, and accepts uploads.

1. A buffered `read` copies cached bytes into the process. A cache miss asks the
   filesystem to fill the page cache first.
2. Read-ahead predicts sequential demand and starts later reads before the
   process asks for them.
3. A buffered `write` dirties cached data. Writeback later sends dirty data to
   storage.
4. `O_DIRECT` requests direct input/output (I/O). It bypasses page-cache data
   transfer when the filesystem accepts the request.

The page cache stores file-backed memory in page-sized units. Current upstream
Linux groups pages in a `folio`, a physically contiguous group managed as one
memory-management unit. A file's `address_space` maps file offsets to those
cached folios. These names explain kernel internals; applications program the
system-call contract.

## Choose the path from the workload

| Technique | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Buffered `read` or `pread` | Reuse, read-ahead, simple synchronous I/O | Durability or bounded cache footprint | One-shot data can displace useful pages | Data is reused or simplicity matters |
| `mmap` | Direct loads from mapped file pages | Device bypass or automatic durability | Faults and writeback appear at memory accesses | Random reads fit a memory-like interface |
| `posix_fadvise` | Gives Linux an access-pattern hint | A guaranteed cache state or fixed read-ahead window | `DONTNEED` is best effort | The application knows its access pattern |
| `RWF_DONTCACHE` | Requests cache dropping after buffered I/O | Direct I/O or a strict no-cache guarantee | Linux added the flag in 6.14; dropping is best effort | Buffered semantics are useful but reuse is not |
| Buffered `write` plus `fdatasync` | Coalesced writes followed by a durability boundary | A bound on pre-sync dirty memory | Throttling can arrive as a latency cliff | The application can batch a durability point |
| `O_DIRECT` | Cache bypass and explicit ownership of buffers | Asynchrony, durability, or speed | Alignment and queue depth become application work | The application owns reuse and concurrency |
| `O_DIRECT | O_DSYNC` | Cache bypass plus synchronous data-integrity completion | Transactional atomicity | Every write pays a completion boundary | Each direct write needs a durability contract |

Do not infer a cold device from a cold page-cache range. Device, virtual-machine,
and storage-service caches can remain warm after `POSIX_FADV_DONTNEED`.

## Cost checks

First ask how expensive a mixed hit and miss stream is. The weighted mean is

```text
expected service = hit_fraction * hit_time
                 + (1 - hit_fraction) * miss_time
```

For a 95% hit fraction, a 4 microsecond hit, and a 1 millisecond miss:

```text
0.95 * 4 us + 0.05 * 1,000 us = 53.8 us
```

The 5% misses dominate the mean. This equation does not estimate a tail
percentile.

Next ask whether a scan will reuse the data. For `passes` complete scans:

```text
buffered = setup + eviction_cost + file/device_rate
         + (passes - 1) * file/cache_rate
direct   = setup + passes * file/device_rate
```

For an 8 GiB file, a 3 GiB/s device, a 30 GiB/s cache path, 0.4 seconds of
eviction cost, and 0.02 seconds of setup, one pass favors direct I/O by this
model. Two passes favor buffered reuse. The model supports the path decision;
it does not price memory pressure or predict either host.

Read-ahead must stay ahead of the consumer long enough to cover device latency
and scheduling variation:

```text
window_bytes >= consumption_bytes_per_second * (latency + jitter)
```

At 1 GiB/s, 80 microseconds of device latency, and 42 microseconds of jitter,
the lower bound is 127.93 KiB. Fetching 128 KiB for one 4 KiB demand has 32x
read amplification if the application never uses the other bytes.

A buffered writer exhausts dirty headroom when production outruns writeback:

```text
headroom_seconds = (dirty_limit - dirty_background)
                 / (producer_rate - writeback_rate)
```

With 2.4 GiB between the two thresholds and a 3 GiB/s rate gap, the model gives
0.8 seconds. Linux thresholds are dynamic. A cgroup, backing device, and global
memory state can change the real stall point.

A direct-I/O path needs enough requests in flight to cover latency:

```text
queue_depth >= ceil(target_rate * latency / request_size)
```

At 3 GiB/s and 100 microseconds, 4 KiB requests need 79 concurrent operations
with binary GiB units. A 1 MiB request needs one. This lower bound omits software
overhead and device queue limits.

Run the checked calculations:

```bash
cargo run -p page-cache-io --example page_cache_costs
```

## Linux experiment

The experiment compares three semantics on the same 16 MiB file:

- increasing-offset buffered 4 KiB reads with `POSIX_FADV_SEQUENTIAL`;
- the same reads in a seeded permutation with `POSIX_FADV_RANDOM`;
- increasing-offset synchronous 4 KiB reads through `O_DIRECT` at queue depth
  one.

Before each process, the harness requests `POSIX_FADV_DONTNEED` and requires
`mincore` to report zero resident pages. Each process is one treatment. A
complete ABBA or BAAB block is one independent analysis unit. Inner reads are
subsamples, not independent trials. The fixed schedule stops on an invalid
attempt and never replaces a period.

The one-read probe checks page residency and `/proc/self/io` accounting. The
write check measures buffered `write`, `fdatasync`, residency, and supporting
global dirty-page counters. Generated assembly and disassembly confirm that the
compiler retained the I/O and content-verification paths.

See [the experiment contract](experiment/README.md) and [measurement
records](measurements/README.md). The raw bundle binds both hosts to one pushed
source commit and one archive digest.

## Measurement boundary

The timings describe the named Amazon Linux kernels, XFS filesystems, Elastic
Block Store devices, compiler flags, and run window in the measurement records.
The paired intervals cover variation across complete process blocks from this
campaign. They do not estimate variation across hosts, kernel versions,
filesystems, devices, vendors, or instruction-set architecture families.

Observed page residency and storage-byte accounting support claims about those
interfaces. They do not prove internal request merging, device-cache state, or
durability. The upstream Linux 7.1 sources in [references.md](references.md)
explain possible mechanisms; the measured hosts ran patched Linux 6.12 kernels.

## Failure checklist

- A new file descriptor does not create a cold cache state. Cache state belongs
  to the file mapping.
- `POSIX_FADV_DONTNEED` is a hint. Verify residency instead of assuming eviction.
- `O_DIRECT` does not imply asynchronous, zero-copy, durable, or faster I/O.
- `fdatasync` supplies a completion boundary. Page residency after the call is
  not evidence of missing durability.
- `/proc/self/io` byte accounting does not identify the completion time of
  durable device I/O.
- `sync_file_range` is not a substitute for `fsync` or `fdatasync` on Linux.
- Mixed buffered, memory-mapped, and direct writes to overlapping ranges demand
  explicit application coordination.
- Dirty ratios are control inputs, not a persistence deadline or a fixed
  percentage of total physical memory.

## Practical rule

Choose buffered I/O when the kernel owns reuse and access prediction. Add
advice when the pattern is known. Add an explicit
sync operation when success means durable data. Choose direct I/O when the
application can own alignment, cache policy, queue depth, and ordering. Measure
the exact path because cache bypass changes who performs the work; it does not
remove the work.
