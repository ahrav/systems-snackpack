# CPU frontend bottlenecks

The frontend predicts the next program counter, translates it, supplies
instruction bytes or cached operations, decodes when needed, and feeds
rename/allocation. A workload is frontend-bound only when this supply leaves
backend allocation capacity unused.

```text
predicted next PC
    |
    +-- direction, target, and return prediction
    +-- instruction-address translation
    +-- instruction bytes: L1I -> lower caches -> memory
    +-- cached operations or decode
    +-- queueing into rename/allocation
```

Each stage answers a different question. Low instructions per cycle does not
identify the limiting stage. Backend dependencies, data-cache misses, branch
recovery, and serialization can produce the same symptom.

## Supply paths differ by processor

Intel documents a Decoded Stream Buffer and legacy decode path. AMD documents
an Op Cache and decoder paths. Some Arm cores document a macro-operation cache.
These names, capacities, restrictions, and performance-monitoring events belong
to specific processor implementations. They are not x86-64 or AArch64
guarantees.

A decoded-operation-cache miss can hurt while L1I still hits. An L1I hit does
not prove that decode supplied enough operations. Instruction translation can
stall either path before byte or operation delivery.

## Compare layout interventions

| Intervention | Intended effect | Main failure mode |
|---|---|---|
| Profile-guided block placement | Increases hot fall-throughs and shortens hot edges | A stale profile optimizes the wrong path |
| Cold outlining | Removes rarely executed bytes from the hot working set | Added branches, calls, and lost optimization exceed hot-path savings |
| Function reordering or BOLT | Places connected hot functions in the final image | A mismatched profile or binary invalidates attribution |
| Targeted padding | Repairs one demonstrated alignment boundary | Padding expands the L1I and instruction-TLB footprint |
| Inlining or unrolling | Removes control transfers or exposes parallelism | Code growth exceeds frontend reach |
| Large executable pages | Increases instruction-TLB reach | L1I and decoded-operation-cache capacity stay unchanged |

Inspect the linked image after every intervention. Source attributes and linker
flags state intent, not final addresses or instructions.

## Evidence boundary

Measure elapsed time, retired instructions, section sizes, symbol addresses,
final instructions, and supported performance-monitoring events. Record event
running time when the kernel multiplexes counters.

Those observations do not isolate L1I, instruction-TLB, decoded-cache, branch
target, prefetch, or prediction costs. Treat that attribution as an inference
until a targeted treatment moves runtime, final layout, and a credible event
together. A result from one host applies only to that host, binary, workload,
and run window.

## Run the model

The Rust example evaluates the accounting model and the cold-outlining
break-even rule:

```bash
cargo run -p cpu-frontend-bottlenecks --example cost_model
cargo test -p cpu-frontend-bottlenecks
```

The model consumes exposed, non-overlapped penalty cycles. Raw miss latency is
not a valid substitute because fetch, translation, decode, and backend work can
overlap.

See the [first-round decision record](rounds/01.md) and [primary
sources](references.md). The [focused Linux experiment](experiment/README.md)
and [measurement contract](measurements/README.md) add final-image, timing, and
counter evidence without changing these architecture boundaries.

The exact-source records cover
[`xxl` x86-64](measurements/2026-07-29-linux-x86-64.md),
[`alg` AArch64](measurements/2026-07-29-linux-aarch64.md), and the
[cross-host boundary](measurements/2026-07-29-linux-cross-host.md).
