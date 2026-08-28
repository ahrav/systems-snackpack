# DRAM and memory-controller behavior

Dynamic random-access memory (DRAM) is not a uniform-latency byte array. A
background stream can increase useful throughput while a dependent lookup waits
longer. Measure that interference before attributing it to a channel, bank,
row, refresh event, or controller policy.

## Model the path before naming a mechanism

A central processing unit (CPU) checks address translation and caches before a
request reaches the integrated memory controller (IMC). The IMC schedules DRAM
commands across channels, ranks, bank groups, banks, rows, and columns. A
last-level-cache miss therefore does not prove a DRAM read or row conflict.

Use a warehouse model: a channel is a road; a rank selects a set of chips; a
bank is an aisle that prepares work independently; a row is a pallet on that
bank's staging table; and a column selects a package from the open pallet.

A row hit selects a column from the open row. A closed-bank access activates a
row first. A row conflict precharges the open row, activates another row, then
selects a column. [`DramTiming`](src/lib.rs) models these device-side command
components. It omits translation, caches, fabric, controller queueing, and
overlap across banks.

## Keep the competing techniques separate

| Technique | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Layout and request ordering | Wasted lines and repeated activation | An unavoidable dependent address | Cache locality, bank locality, and parallelism can conflict | Measured work rises within the latency budget |
| Independent batching | Too little memory-level parallelism | Excess bytes or a saturated path | Extra requests consume core and controller capacity | Throughput rises within latency and traffic budgets |
| Channel and non-uniform memory access (NUMA) placement | Aggregate path capacity | One dependent load's latency | Firmware mapping and page placement control participation | Exact topology and traffic evidence show imbalance |
| Offered-load control | Queueing and interference | Poor solo latency | Limiting traffic reduces peak throughput | A latency objective matters more than maximum traffic |
| Read/write batching | Bus direction changes | Bank conflicts or durability | Batches create bursts and can delay reads | Semantics permit batching and measurement shows a benefit |
| Physical mapping control | A proven bank, row, or channel placement need | Firmware changes | Mapping is platform-specific and often hidden | A controlled appliance has direct mapping evidence |

## Use arithmetic as a consistency check

The following values illustrate the model; they do not describe either host.
With column latency `14 ns`, burst time `2.5 ns`, activation delay `14 ns`, and
precharge time `14 ns`, the device components are:

```text
row hit      = 14 + 2.5            = 16.5 ns
closed bank  = 14 + 14 + 2.5       = 30.5 ns
row conflict = 14 + 14 + 14 + 2.5  = 44.5 ns
```

A mix of 50% hits, 20% closed banks, and 30% conflicts has a `27.7 ns`
expected device component. The CPU-observed load also includes translation,
caches, fabric, queueing, and return travel.

Little's law estimates concurrency for one request class:

```text
requests_in_flight = target_bytes_per_second * latency_seconds
                     / useful_bytes_per_request
```

At `20 GB/s`, `100 ns`, and `64` useful bytes per request, the result is
`31.25`. The workload needs about 32 independent requests in flight. One
dependent pointer chain cannot expose them. The runnable
[`dram_cost_model`](examples/dram_cost_model.rs) performs these checks. They
are accounting models, not elapsed-time predictions or a DRAM simulator.

## Focused experiment

[`dram_bench.c`](experiment/dram_bench.c) compares the same 512 MiB dependent
chain with idle workers and with eight read-only streaming workers. The probe
runs on CPU 0. Workers run on CPUs 1 through 8 and own private 128 MiB buffers.
Both treatments create the same threads and buffers. The loaded treatment
releases the workers during the timed chain.

An 8 KiB cache-resident chain checks for effects that also reach its earlier
timing window. A stable small control does not exclude work specific to the
later large-chain window.

[`run_processes.py`](experiment/run_processes.py) runs 12 four-process `ABBA`
or `BAAB` primary blocks and four loaded/loaded A/A blocks. A/A means both
labels run the same loaded treatment. Each letter starts a fresh process. One
complete block, not a pointer load or stream chunk, is one replication. The
fixed campaign contains 64 fresh process identifiers (PIDs) and no replacements.

The stream counter includes complete chunks only. Its interval starts at worker
release and ends after all workers join. If `W` is the worker count and `C` is
the chunk size, useful source bytes lie in:

```text
counted_bytes <= actual_useful_bytes <= counted_bytes + W * C
```

Here, `W * C` is 2,097,152 bytes. The count measures source bytes consumed by
the stream loops, not cache-line fills, fabric traffic, or IMC bus bytes.

## Exact-source first visit

Both accepted campaigns used source commit
`8ad95023e53c516499c1c85631582c52ebd63921` and source-archive SHA-256
`1c8669600b7c28645ee50242c0934d2d5ec1110afd98e360d757bc636dd095ef`.
The Arm binary SHA-256 is
`24d707648f0db68c937910b7978367c540422cbe6a53452d616fbe36f0465c54`.
The `xxl` binary SHA-256 is
`4db104329c6bd1a6135c05c6b2eed84559939173a85e6a4dec27bec022786264`.

Each host ran 12 primary blocks and four A/A blocks, for 64 fresh PIDs. Every
final large-window process and probe-thread minor- and major-fault field was
zero. Every process bound future allocations to NUMA node 0 with Linux
`MPOL_BIND`, a memory policy that restricts allocation to the selected node.

| Observation | Required AArch64 host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Idle median large-chain ns/load | `140.4363434612751` | `161.2875382900238` |
| Loaded median large-chain ns/load | `198.96543346345425` | `174.85686768591404` |
| Loaded/idle ratio | `1.4178028483779435` | `1.0837706882265017` |
| 95% between-block interval | `[1.4139425735275073, 1.4216736623564883]` | `[1.0827047826765401, 1.084837643143437]` |
| Small-control ratio | `1.0031464495214135` | `1.0016089322922408` |
| Loaded-path B/A A/A ratio | `0.998369422455882` | `1.000293329134667` |
| Median useful-source lower bound, GiB/s | `133.912642668` | `77.7596938225` |

GiB/s means gibibytes per second. The 95% Student t intervals cover
between-block variation for one exact host, binary, input, placement, and run
window. They do not compare Arm with x86. Neither guest exposed an integrated
memory-controller performance-monitoring unit (PMU), so the campaigns cannot
attribute the delay to a DRAM mechanism.

See the [Arm record](measurements/2026-08-28-arm.md), the
[`xxl` record](measurements/2026-08-28-xxl.md), and the
[cross-host boundary](measurements/2026-08-28-comparison.md) for exact ranges,
dispersion, scheduler counters, code generation, and campaign rejection rules.

## Evidence boundary

Elapsed time, useful-source-byte bounds, process resource counters, affinity
canaries, mapping observations, checksums, and linked disassembly are measured.
The workers plausibly increased pressure somewhere in the shared memory
hierarchy. The evidence does not identify DRAM-only latency, controller
saturation, bank conflicts, row hits, refresh, channel mapping, queue policy,
or a processor-family rule.

## Selection guide

1. Separate cache-resident, local-memory, and remote-memory behavior.
2. Measure solo and loaded latency as separate outcomes.
3. Record useful source bytes and controller traffic separately.
4. Reduce dependencies and unused bytes before adding concurrency.
5. Add independent work only inside latency and traffic budgets.
6. Limit background traffic when loaded latency violates the objective.
7. Use row or bank explanations only with mapping or controller evidence.
8. Keep refresh, error correction, scrubbing, and application traffic distinct.

See [`experiment/README.md`](experiment/README.md) for exact-source commands,
[`rounds/01.md`](rounds/01.md) for the frozen claim, and
[`references.md`](references.md) for primary sources and version boundaries.
