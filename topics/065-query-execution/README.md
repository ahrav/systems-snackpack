# Query execution: calls, batches, and morsels

This controlled scan separates per-row indirect dispatch, a selection-buffer batch,
and a fused loop over identical columns. A separate concurrent allocator claims
morsels and joins workers before combining private sums. It is not a SQL engine,
a NUMA-aware scheduler, or a database benchmark.

## Contracts

A row contributes when `region & mask == 0` and validity is one. Amounts sum modulo
2^64; zero survivors return zero. Generated inputs have amounts 1..=1000 and cannot
overflow at the tested size. SQL null-on-empty, decimal overflow, and floating-point
reassociation semantics are deliberately outside this model.

`Columns::new` checks lengths and validity. Range ends use remaining length to avoid
addition overflow. Selection positions are native `usize`, not the illustrative
four-byte positions in the lesson. Buffers reserve once per `batched` invocation
and are reused within that query; allocation is included in the measured kernel.

Relaxed compare-and-swap claims disjoint indexes. Inputs are immutable and created
before spawning. Joins synchronize completion before reduction. Exhausted claims
do not prove that all claimed work completed. No mutable hash-table publication
protocol is implemented here.

## Reproduce

```bash
cargo test -p topic065-query-execution
cargo run --release -p topic065-query-execution --example probe -- batch 1048576 63 1024 32
sh topics/065-query-execution/scripts/run-linux.sh final
```

The runner requires Linux, Rust >=1.93, Python 3, GNU objdump, taskset, and sha256sum.
It uses `-C target-cpu=native`; keep each binary on its recorded machine. It emits
source and binary hashes, tests, compiler assembly, linked disassembly, host facts,
and independent-process observations into `evidence/` in the current directory.
Run in an extracted scratch archive, not a dirty checkout. Input hashes are recorded
before Cargo prunes the full-workspace lockfile to the extracted topic. The derived
lockfile hash is recorded separately; the crate has no external dependencies.

## Experiment controls

Input has 1,048,576 rows, scrambled region bytes, bounded amounts, and one null per
17 rows. Masks 63 and 1 select roughly 1/64 and 1/2 before validity. Compare row
calls and batch sizes 64, 1024, 16384 against fused scans. Include fused/fused A/A.
Each comparison has six adjacent process pairs, three in each order. Each process
performs setup and oracle evaluation, a separately timed first treatment scan,
two warmup scans, then 32 repeated warm scans. Those repetitions are one sample.

Process elapsed time, setup time, first scan, and warm time remain separate. The
first scan follows an oracle scan and is not cold-cache evidence. Each process is
pinned to the first allowed CPU and allocates its own input there. Four correctness
workers inherit that affinity; they exercise concurrency, not multicore speedup.
Thread creation and morsel checks occur after scan timing. Host load and frequency
are not controlled. Treat medians and min/max ranges as descriptive, not confidence
intervals or population claims. Dataset generation and oracle work are not included
in warm scan latency. No query-time compilation occurs.

## Interpretation

An execution batch amortizes calls. SIMD is a property to verify in generated code.
A morsel is a scheduling range and may contain many execution batches. Fusion saves
position writes and reads but changes optimizer visibility too. These treatments
are packages of effects; a timing ratio alone cannot attribute a speedup to calls,
branches, vector width, cache misses, or selection traffic.

The lesson's cost model is illustrative. A 1024-row batch with region, amount,
validity and four-byte selection positions models 14,336 live bytes. This executable
uses eight-byte positions on both tested hosts, so full-capacity modeled storage
would be 18,432 bytes. Physical memory traffic must be measured separately.

See [references](references.md), [first round](rounds/01.md), and the measurement
report for exact observations and retained evidence identities.
