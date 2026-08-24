# Performance portability: choose vector width from evidence

Wider vectors perform more useful updates per instruction. They can also change
the available execution ports, clock rate, tail handling, and fixed dispatch
cost. Instruction-set support establishes legality, not the fastest width.

Single Instruction, Multiple Data (SIMD) applies one instruction to two or more
independent values. A lane is one value inside that instruction. The experiment
keeps 96 double-precision lanes of useful work fixed while comparing scalar,
128-bit, 256-bit, and 512-bit implementations where the host supports them.

## Make three decisions separately

1. **Legality:** Detect the exact required features before entering a specialized
   function. Keep a scalar implementation as the correctness oracle.
2. **Code generation:** Inspect the deployed binary. Confirm the intended lane
   width and operation appear in the measured loop.
3. **Profitability:** Measure the real request size, active-core count, memory
   traffic, and follow-on workload on each processor model.

Scalar code minimizes dispatch and tail costs. A 128-bit path gives two
double-precision lanes and exists on both measured architectures. Advanced
Vector Extensions 2 (AVX2) gives four lanes on x86-64. Advanced Vector Extensions
512 (AVX-512) gives eight lanes where the required feature subset exists. Arm
Scalable Vector Extension (SVE) uses an implementation-selected vector length;
this first visit records SVE availability but does not execute an SVE path.

## Bound throughput before timing

The useful rate cannot exceed either memory delivery or compute execution:

```text
rate = min(memory_bytes_per_second / bytes_per_element,
           cycles_per_second * vector_operations_per_cycle * lanes_per_vector)
```

For 32 GB/s and eight bytes per element, memory caps the rate at four billion
elements per second. A four-lane path at 3 GHz and two vector operations per
cycle has a 24-billion-element compute bound, so extra lanes cannot help until
memory traffic changes. [`roofline_elements_per_second`] evaluates this bound.

When fixed useful work halves the dynamic instruction count, a measured clock
ratio changes the elapsed-time expectation:

```text
candidate_time / baseline_time
    = candidate_cycle_work / baseline_cycle_work
      / (candidate_clock / baseline_clock)
```

This is a diagnostic model, not proof of a frequency mechanism. An instruction
count ratio can stand in for cycle work only when the paths have equal
per-instruction cycle cost. Port pressure, dependencies, and measurement scope
must also match.

Short inputs can favor a narrower path even when a wider loop has greater
steady-state throughput:

```text
time(elements) = dispatch + elements / measured_rate + attributed_follow_on
```

[`PathCost`], [`fixed_work_time_ns`], and [`break_even_elements`] make the fixed
costs explicit. Dispatch includes feature selection and setup. Follow-on time
includes only a cost the experiment can attribute to that path. Do not insert a
processor-family folklore constant.

## What each width solves

| Path | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Scalar | Tiny inputs, tails, universal fallback | Lane parallelism | More instructions for independent work | Inputs are short or no vector path passes its gate |
| 128 bit | Portable fixed-width parallelism across these two architectures | Memory limits or dispatch overhead | Limited to two double lanes | It wins on the target mix or provides the simplest common path |
| 256 bit | Four double lanes with AVX2 on x86-64 | AVX-512-only operations | Documented Intel clock policies classify instruction mix as well as width | It wins request-level measurements and controls code size |
| 512 bit | Eight double lanes and AVX-512 operations | Bandwidth, tails, or service-wide side effects | Benefit depends on processor model, instruction mix, and active cores | Model-specific measurements include the follow-on workload |
| SVE | One vector-length-agnostic Arm loop | A universal physical width or speedup | Correct code must tolerate the runtime vector length | An SVE implementation beats the fixed-width path on supported Arm targets |

`vzeroupper` addresses the legacy Streaming SIMD Extensions (SSE) to AVX
upper-register transition. It does not reset a processor frequency policy.
Likewise, a compiler vectorization cost model sees one function. It cannot price
latency imposed on later request phases or a sibling hardware thread.

## Focused experiment

[`experiment/width_bench.c`](experiment/width_bench.c) runs the same recurrence
over 96 logical double-precision chains. Twelve independent accumulators expose
instruction-level parallelism without changing useful work. Every mode computes
`x = fused_multiply_add(multiplier, addend, x)`. The scalar check permits only a
small floating-point reduction-order difference.

[`experiment/run_experiment.py`](experiment/run_experiment.py) launches fresh
processes in seed-shuffled ABBA and BAAB blocks. One complete four-process block
is one replication. It reports a geometric candidate-to-baseline time ratio and
a two-sided 95% paired Student-t interval over block log contrasts. An identical
treatment A/A comparison screens label and position imbalance.

[`experiment/run_host.sh`](experiment/run_host.sh) binds a Git archive to one
authorized Linux target, records the host and toolchain, runs Rust and C
correctness checks, captures generated code, executes the fixed schedule, and
runs the independent receipt validator. See [`rounds/01.md`](rounds/01.md) for
the acceptance contract. Final host records belong under [`measurements/`](measurements/).

## Evidence boundary

The timing interval covers between-block variation during one run window. The
primary timer covers only the fixed-work kernel after same-mode warmup. Linux
`perf stat` counters cover process startup, warmup, and the main kernel because
they surround the child process. The x86-64 run groups core cycles with reference
cycles when the model exposes both events. The Arm run records core cycles only.

Cycle-to-reference-cycle ratios can support a clock-rate explanation on the
tested x86 processor. They cannot prove a frequency-license transition. Virtual
machine scheduling, thermal drift, shared-machine work, and shorter steal
intervals can remain. A result names one host, compiler, binary, input, CPU
placement, active-core state, and run window. It is not an instruction-set-wide
claim.

## Selection guide

1. Keep scalar as the oracle and fallback.
2. Dispatch only after exact feature detection.
3. Inspect the generated loop for every deployed target.
4. Measure fixed request sizes with process-level, order-balanced replication.
5. Include startup, tails, and attributable follow-on work in the decision.
6. Separate memory-bound workloads from compute-bound workloads.
7. Remeasure by processor model, compiler, active-core count, and service mix.

Primary sources and their version boundaries are in
[`references.md`](references.md).

[`roofline_elements_per_second`]: crate::roofline_elements_per_second
[`PathCost`]: crate::PathCost
[`fixed_work_time_ns`]: crate::fixed_work_time_ns
[`break_even_elements`]: crate::break_even_elements
