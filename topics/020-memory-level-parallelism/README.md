# Memory-level parallelism

Memory latency overlaps only when software exposes independent addresses and
every request queue on the path has capacity. Socket bandwidth does not shorten
a dependent pointer chain.

## Model

For one request class over one stable interval:

```text
N = completion_rate * residence_time
useful_bandwidth = completion_rate * useful_bytes_per_completion
```

Keep request populations and scopes aligned. A core-side demand-read occupancy
event, socket-wide controller bytes, and end-to-end load latency do not form one
Little's-law identity.

For the random-load probe:

```text
seconds_per_load >= max(
    effective_latency / effective_concurrency,
    load_issue_interval,
    transferred_bytes / available_bandwidth
) + software_overhead
```

`effective_concurrency` includes software independence, compiler code
generation, the out-of-order window, load and miss queues, translations, cache
levels, the coherent fabric, and the memory system. A chain-width plateau does
not reveal any one queue's size.

## What the crate isolates

[`Cycle`](src/lib.rs) builds one deterministic random cycle in 64-byte nodes.
The node size is an object-layout fact, not a portable cache-line-size claim.
Both treatments use the same cycle and perform the same total useful-load
count:

- `walk_one` carries one load-to-address dependency.
- `walk_eight` keeps eight cursor dependencies independent.

The experiment times setup, a full-cycle warm traversal, and steady traversal
separately. A recorded seed shuffles four AB and four BA process pairs. Four
balanced A/A process pairs exercise both labels and schedule paths. The
analysis unit is one complete pair, not an inner load.

Run one process:

```bash
cargo run --release --package memory-level-parallelism \
  --example chain_probe -- \
  --lanes 1 --nodes 4194304 --loads 33554432
```

Run the repository benchmark smoke program:

```bash
cargo bench --package memory-level-parallelism --bench chain_sweep
```

Run the retained Linux workflow from the repository root:

```bash
topics/020-memory-level-parallelism/experiment/run_remote.sh \
  "$PWD" /tmp/topic20-evidence 0
```

## Evidence boundaries

The reviewed final disassembly must show one dependent cursor or eight
lane-local cursors. Symbol presence alone is insufficient. The code shape does
not prove overlap. The paired elapsed-time result is consistent with latency
overlap when eight chains improve throughput.
Model-specific core, cache, and memory-controller counters are required before
attributing the effect to a named queue or to DRAM.

Cache-line crossings and memory disambiguation change the request population:

- a load crossing a cache line can consume two line accesses and split-load
  resources;
- a younger load can wait or replay when an older unresolved store may alias;
- failed store forwarding can serialize an overlapping load.

The focused probe removes stores. On the two measured Linux hosts, recorded
cache geometry establishes that each 64-byte node begins on its own cache line.
The probe does not measure crossing or disambiguation costs. See
[references](references.md) for model-specific events that test them.

## Failure checks

- Use a working set larger than the relevant last-level cache.
- Pin the process and record its simultaneous-multithreading sibling.
- Keep page faults and graph construction outside steady timing.
- Inspect the final native binary.
- Keep all failed and partial attempts; exclude incomplete pairs from the fixed
  estimator without replacing them.
- Record transparent-huge-page, NUMA, compiler, kernel, and CPU boundaries.
- Do not generalize a host result to an instruction set or processor family.

See [round 1](rounds/01.md) for the decision record and
[measurements](measurements/README.md) for retained evidence.
