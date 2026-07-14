# Topic 4: Reading x86-64 and AArch64 assembly for performance

Disassembly shows the instruction stream. It does not show the complete
execution cost. Interpret it through the target CPU and the runtime trace.

## Four-layer mental model

1. **Source semantics.** Identify aliases, alignment promises, loop-carried
   dependencies, branch probabilities, and active vector lanes.
2. **ISA stream.** Read instructions, operands, addressing modes, and control
   flow. Record the exact target and compiler options.
3. **Core execution.** Map instructions to front-end work, the operand dependency
   graph, execution resources, and the critical path for one named CPU.
4. **Runtime trace.** Account for actual addresses, cache lines, pages, branch
   outcomes, cache misses, and available memory-level parallelism.

A useful loop lower bound is:

```text
T_loop >= max(T_front_end, T_critical_path, T_resources, T_memory)
```

Each term needs its own evidence. Their maximum is a lower bound on loop time.

## Five mechanics that resist mnemonic-level reasoning

| Mechanic | What the assembly establishes | Required boundary |
|---|---|---|
| Macro-fusion | An adjacent compare and branch form a fusion candidate. AArch64 `cbz` is one instruction, not a fused pair. | Eligibility depends on the named core. Adjacency does not prove fusion. |
| Division | Compile-time `/ 7` permits a multiply-high and shift sequence. A runtime-invariant divisor can retain hardware division. | Compare the emitted code first. The compiler can specialize, hoist, or transform either case. |
| False dependencies | Operand-to-operand dependency edges can differ between CPU models. | A target-specific zero idiom can break an edge. On unaffected CPUs, it can add front-end work. |
| Gather | One mnemonic forms one address for each active lane. | Count distinct lines and pages. One mnemonic does not imply one memory transaction; memory-level parallelism also matters. |
| Split loads | A load crosses a cache line when `(address mod line_size) + width > line_size`. | Separate within-line, cross-line, and cross-page cases. Rust alignment validity is independent of hardware tolerance. |

For division, define the per-iteration hardware cost as `C_div`, the reciprocal
path cost as `C_fast`, and setup as `C_setup`:

```text
T_hw    = N * C_div
T_recip = C_setup + N * C_fast
N > C_setup / (C_div - C_fast)
```

The final inequality is the derived crossover when `C_div > C_fast`. Measure
the costs on the target CPU instead of assigning a scalar cost to a mnemonic.

## Match each tool to one question

| Technique | Evidence | Limit |
|---|---|---|
| Disassembly | Emitted instructions, operands, and control flow. | It omits dynamic addresses, cache state, branch outcomes, and realized overlap. |
| Vendor guides | Vendor-documented behavior for named processor families or cores. | Keep each statement within the guide's revision and CPU scope. |
| uops.info | Third-party operand latency, throughput, port, and micro-op measurements for listed CPUs. | Intel results do not establish costs for every x86-64 CPU. |
| `llvm-mca` | Models dispatch/backend scheduling, register-dependency, and execution-resource pressure for a selected LLVM scheduling model. | It omits fetch/decode, branch prediction, and the real cache hierarchy. `Block RThroughput` is a theoretical cycles-per-iteration quantity under its documented assumptions, not a wall-clock prediction. |
| Performance monitoring units (PMUs) | Event counts from the named CPU and workload. | Check event definitions, privilege scope, multiplexing, and run variance. |
| Wall clock | Elapsed time across a stated input and code boundary. | It combines every cost inside that boundary. |

## Focused experiment: constant versus runtime divisor

The two kernels use divisor `7`, the same wrapping multiply-add, the same
loop-carried state, and the same iteration count. The only intended treatment
difference is whether the callee receives the divisor as an argument.

Run the equality check:

```bash
cargo run -p systems-snackpack-topic-004 --example compare_division
```

Run the whole-kernel benchmark:

```bash
cargo bench -p systems-snackpack-topic-004 --bench division_chain
```

Generate release assembly:

```bash
cargo rustc -p systems-snackpack-topic-004 --release --lib -- --emit=asm
```

Generated `target` files are absent from the `colgrep` index. Search them
directly when checking the emitted sequence:

```bash
rg -n 'divide_(constant|runtime)_chain|madd|udiv|umulh|b\.ne' \
  target/release/deps/systems_snackpack_topic_004-*.s
```

On the recorded Apple M1 Pro toolchain, the runtime loop contains `madd`,
`udiv`, `subs`, and `b.ne`. The constant loop contains `madd`, `umulh`, `sub`,
a corrected `add ... lsr #1`, `lsr`, `subs`, and `b.ne`. These are local codegen
observations, not timing evidence.

The benchmark runs 10,000,000 loop-carried iterations per sample. It uses six
warm-up pairs and 21 measured samples per path. It alternates path order, uses
deterministic per-trial seeds, and reports the median whole-kernel elapsed time.
`black_box` appears only at call boundaries.

The two clock reads span one non-inlined kernel call. The interval includes the
call and return plus multiply-add, division or replacement sequence, and loop
control. Argument and result `black_box` calls, warmup, validation, sorting,
process startup, and output occur outside the interval.

## Measured, observed, and inferred

The 2026-07-14 Apple M1 Pro run measured these whole-kernel medians:

| Path | Total | Per iteration |
|---|---:|---:|
| Constant divisor | 32,283,500 ns | 3.228 ns |
| Runtime divisor | 38,533,541 ns | 3.853 ns |

The measured runtime/constant ratio is `1.194x`. The timer does not isolate
divider or `umulh` latency. The result does not establish a ratio for another
CPU, compiler, or input.

The instruction lists above are observed codegen. The lower-bound and crossover
equations are derived models. Vendor guides document named targets; uops.info
reports third-party measurements for listed CPUs. Keep these evidence classes
separate.

See the [measurement record](measurements/2026-07-14-m1-pro.md) and
[reference scopes](references.md).

## Failure checklist

- Name the CPU, compiler, flags, and measurement boundary.
- Trace operand dependencies instead of assigning costs to mnemonics.
- Treat adjacent compare-and-branch instructions as fusion candidates.
- Count active gather lanes, distinct cache lines, and pages.
- Classify loads as within-line, cross-line, or cross-page.
- Check Rust pointer validity separately from hardware access behavior.
- Pair modeled throughput with PMU or wall-clock evidence.
