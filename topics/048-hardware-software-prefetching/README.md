# Hardware and software prefetching

A processor stalls when an **ordinary load**, the instruction that actually
needs a value, waits for a **cache line**, the fixed-size block transferred by
the cache hierarchy. Prefetching starts that memory request earlier. It changes
timing, not correctness: a prefetch is a hint, may be ignored, and cannot
replace the load.

## Start with the access pattern

Imagine a warehouse picker. The current order names one bin, and an index array
names later bins. The fastest fix is usually to shorten the route: pack useful
fields, process nearby bins together, or batch independent orders. Hardware
prefetchers work like an automatic dispatcher. They recognize regular routes
such as sequential or fixed-stride access. A software prefetch is a manual note
for a future bin whose valid address the program can compute first.

An **irregular gather**, which loads records named by an index array whose
addresses do not form a simple pattern, is eligible for software prefetch only
when all of these hold:

- the region waits on data rather than instructions, branches, or locks;
- a future address is valid and known before the demand load;
- independent work can cover the request latency;
- the prefetched line is still useful when demand arrives;
- the extra instruction, traffic, and cache footprint repay their cost.

A dependent pointer chase fails the third condition. The current node contains
the only address of the next node, so a hint issued after reading that address
cannot create useful lead time. Interleave independent traversals, batch keys,
or change the representation instead.

## Keep each technique's contract separate

| Technique | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Layout or blocking | Wasted bytes and poor locality | An unavoidable random dependency | Changes representation and maintenance cost | The interface permits packed or batched work |
| Hardware prefetch | Recognizable regular streams | Arbitrary future addresses hidden in data | Model-specific coverage and possible pollution | Production access is sequential or fixed-stride |
| Compiler prefetch | A compiler-proven future load | Semantic facts the compiler cannot establish | Version-sensitive and often conservative | The generated image already proves the desired request |
| Explicit software hint | A valid irregular future address known early | Correctness, synchronization, or dependency chains | Tuning, portability, traffic, and cache cost | Exact-source evidence shows a whole-workload win |
| Interleaved ordinary loads | Several independent dependency chains | A single unavoidable chain | More live state and code complexity | Keys or traversals can be batched |

The checked C experiment uses GNU Compiler Collection (GCC)
`__builtin_prefetch(address, 0, 0)`. Locality `0` asks for low temporal
locality, meaning little near-term reuse is expected. GCC may emit a different instruction or no instruction on another
target. The address expression is still evaluated, so forming it must be valid
under the source language even though the hint itself is not a fault-handling
or synchronization mechanism.

## Screen a candidate with arithmetic

If a miss takes 240 cycles and useful independent work takes 6 cycles per loop
iteration, the request needs about 40 iterations of lead time:

```text
lead_iterations = ceil(240 / 6) = 40
```

At one 64-byte line per iteration, those requests represent 2,560 bytes of
in-flight cache footprint. Arriving earlier can therefore trade latency for
cache occupancy and memory traffic.

A first-order throughput ceiling is the smallest of three limits. A central
processing unit (CPU) is the processor executing the loop:

```text
iterations_per_cycle <= min(
    CPU execution limit,
    concurrent_misses / (miss_latency_cycles * misses_per_iteration),
    memory_bytes_per_cycle / bytes_per_iteration
)
```

With a CPU limit of 0.5 iterations per cycle, 12 concurrent misses, 240-cycle
latency, one matching miss per iteration, 16 memory bytes per cycle, and 64
bytes per iteration, the limits are 0.5, 0.05, and 0.25. Concurrency is the
smallest modeled limit. With two matching misses per iteration, the concurrency
limit would be 0.025 iterations per cycle. A prefetch can help only if it
increases useful overlap without creating a smaller bandwidth or execution
limit.

If a hint costs 0.5 cycle per iteration and a useful hint avoids 20 stall
cycles, at least `0.5 / 20 = 0.025`, or 2.5%, must be useful before counting
pollution or extra traffic. [`src/lib.rs`](src/lib.rs) implements these checks.
They are arithmetic screens, not elapsed-time predictors.

## Focused experiment

[`experiment/prefetch_bench.c`](experiment/prefetch_bench.c) compares a scalar
demand-only gather with the same gather plus one low-locality read hint. Each
record has a 64-byte stride. The program's 4,096-byte-aligned allocation plus
the 64-byte cache lines reported by both measured hosts puts each record on a
separate line; the structure-size assertion alone would prove only the stride.
A deterministic permutation visits every record exactly once per pass. The
program checks the sum, reports page faults and processor migration around the
timed kernel, and keeps allocation, initialization, and warmup outside
steady-state time.

[`experiment/run_campaign.py`](experiment/run_campaign.py) uses fresh processes
and complete ABBA/BAAB blocks. A is demand-only and B is one fixed prefetch
distance. An independent A/A control sends demand-only work through both
labels. One complete block, not a loop access or pass, is one replication.

[`experiment/run_host.sh`](experiment/run_host.sh) binds a run to a sealed Git
archive, host identity, build flags, source and binary digests, process order,
and linked code. [`experiment/analyze.py`](experiment/analyze.py) computes one
log-time contrast per complete block and reports a descriptive Student-t
interval. [`experiment/validate_receipts.py`](experiment/validate_receipts.py)
checks the receipt and independently recomputes the analysis.

See [`experiment/README.md`](experiment/README.md) for commands and
[`rounds/01.md`](rounds/01.md) for the frozen acceptance contract. Final
exact-host observations belong under [`measurements/`](measurements/).

## Evidence boundary

Elapsed time establishes one workload result on one exact host and binary.
Disassembly establishes the emitted instruction. Correct checksums establish
functional equivalence for the tested input. Those facts do not identify which
cache served a line, count hardware-prefetch requests, measure memory-level
parallelism, or prove a processor mechanism. Those claims need simultaneous,
model-specific performance-monitoring counters or other direct evidence.

## Selection guide

1. Prove the region waits on memory.
2. Reduce bytes and dependency depth with layout, blocking, or batching.
3. Let production-state hardware prefetch handle regular streams.
4. Expose independent work before adding a hint.
5. Use a software hint only for a valid future address known early enough.
6. Inspect the exact linked binary and test several distances as exploration.
7. Confirm one fixed candidate with fresh, order-balanced processes and A/A.
8. Keep it only when the complete workload improves without unacceptable
   bandwidth, cache, tail-latency, code-size, or portability cost.

Primary sources and their version boundaries are in
[`references.md`](references.md).
