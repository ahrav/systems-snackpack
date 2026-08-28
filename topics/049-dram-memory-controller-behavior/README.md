# DRAM and memory-controller behavior

Dynamic random-access memory (DRAM) is not a uniform-latency byte array. A
request that reaches memory competes for controller queues, command and data
buses, banks, open rows, direction changes, and refresh opportunities. This
matters because a background stream can increase useful throughput while a
dependent lookup waits longer.

## Model the path before naming a DRAM mechanism

A central processing unit (CPU) checks address translation and caches before a
request reaches the integrated memory controller (IMC). An IMC schedules DRAM
commands across channels, ranks, bank groups, banks, rows, and columns. A
last-level-cache miss therefore does not by itself prove a DRAM read or a row
conflict.

Use a warehouse model:

- a channel is a road with shared command and data wires;
- a rank is a selected set of chips that supplies the channel width;
- a bank is an aisle that can prepare work independently;
- a row is a pallet placed on that bank's staging table;
- the row buffer is the staging table;
- a column selects a package from the open pallet.

A row hit selects a column from the open row. A closed-bank access activates a
row first. A row conflict precharges the open row, activates another row, then
selects a column. [`DramTiming`](src/lib.rs) models these device-side command
components. It does not model translation, caches, fabric, controller queueing,
or overlap across banks.

## Keep the competing techniques separate

| Technique | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Layout and request ordering | Wasted lines and repeated activation | An unavoidable dependent address | Cache locality, bank locality, and parallelism can conflict | Measured useful work rises without unacceptable tail cost |
| Independent batching | Too little memory-level parallelism | Excess bytes or a saturated path | More requests consume core and controller capacity | Throughput rises inside the latency and traffic budgets |
| Channel and NUMA placement | Aggregate path capacity | One dependent load's latency | Firmware mapping and page placement control participation | Exact topology and traffic evidence show imbalance |
| Offered-load control | Queueing and interference | Poor solo latency | Reduces peak throughput | A latency objective matters more than maximum traffic |
| Read/write batching | Bus direction changes | Bank conflicts or durability | Creates bursts and can delay reads | Semantics permit batching and measurement shows a benefit |
| Physical mapping control | A proven bank, row, or channel placement need | Firmware or hardware changes | Mapping is platform-specific and often hidden | A controlled appliance has direct mapping evidence |

## Use arithmetic as a consistency check

The example uses illustrative values, not either measured host. With column
latency `14 ns`, burst time `2.5 ns`, activation delay `14 ns`, and precharge
time `14 ns`, the modeled device components are:

```text
row hit     = 14 + 2.5           = 16.5 ns
closed bank = 14 + 14 + 2.5      = 30.5 ns
row conflict= 14 + 14 + 14 + 2.5 = 44.5 ns
```

A mix of 50% hits, 20% closed banks, and 30% conflicts has a `27.7 ns`
expected device component. The CPU-observed load can take longer because it
also includes translation, caches, fabric, queueing, and return travel.

Little's law estimates the request concurrency needed for one defined request
class:

```text
requests_in_flight = target_bytes_per_second * latency_seconds
                     / useful_bytes_per_request
```

At `20 GB/s`, `100 ns`, and `64` useful bytes per request, the result is
`31.25`, so the workload needs about 32 independent requests in flight. One
dependent pointer chain cannot expose them.

[`examples/dram_cost_model.rs`](examples/dram_cost_model.rs) runs these checks.
They are accounting models, not elapsed-time predictions or a DRAM simulator.

## Focused experiment

[`experiment/dram_bench.c`](experiment/dram_bench.c) compares the same large
dependent chain with idle workers and with read-only streaming workers. Both
treatments create the same threads and private buffers. The loaded treatment
releases the workers during the timed chain. A small cache-resident chain checks
for broad scheduler or frequency effects.

[`experiment/run_processes.py`](experiment/run_processes.py) uses 12 complete
ABBA/BAAB process blocks and four loaded/loaded A/A blocks. Each letter is a
fresh process. One complete block, not a pointer load or stream chunk, is one
replication. [`experiment/analyze.py`](experiment/analyze.py) reports the
loaded/idle log-time contrast and a host-specific interval.

The stream counter includes only complete chunks. Its interval is the full run
epoch: worker release, the all-worker first-chunk acknowledgement, the small
control, and the large probe. If `W` is the worker count and `C` is the chunk
size, useful source bytes in a loaded run lie in:

```text
counted_bytes <= actual_useful_bytes <= counted_bytes + W * C
```

The idle treatment has exact zero lower and upper bounds. These counts measure
source bytes consumed by the stream loops. They do not measure cache-line
fills, interconnect traffic, or IMC bus bytes.

See [`experiment/README.md`](experiment/README.md) for exact-source commands and
[`rounds/01.md`](rounds/01.md) for the frozen claim.

## Evidence boundary

Elapsed time measures one exact workload. Disassembly proves the final binary's
dependency and scan shapes. Checksums prove the tested transitions. Host
metadata records topology, page policy, and counter exposure. Without matching
model-specific controller counters, these facts do not identify row hits,
bank conflicts, refresh, channel mapping, controller saturation, or a literal
scheduling policy.

## Selection guide

1. Separate cache-resident, local-memory, and remote-memory behavior.
2. Measure solo and loaded latency as separate outcomes.
3. Record useful source bytes and physical controller traffic separately.
4. Reduce dependencies and unused bytes before adding concurrency.
5. Add independent work only inside the latency and traffic budgets.
6. Limit background traffic when loaded latency violates the objective.
7. Use row or bank explanations only with exact mapping or controller evidence.
8. Keep refresh, error correction, scrubbing, and application traffic distinct.

Primary contracts and version boundaries are in
[`references.md`](references.md).
