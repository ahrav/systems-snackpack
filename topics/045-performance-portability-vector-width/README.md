# Performance portability: choose vector width from evidence

Wider vectors perform more useful updates per instruction. They can also use a
different set of arithmetic pipelines, change clock rate, require special work
for leftover elements, and add one-time path-selection or setup cost. The
specialist terms for these effects are execution ports, tail handling, and
dispatch cost. Instruction-set support establishes legality, not the fastest
width.

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

The useful rate cannot exceed either memory delivery or compute execution. In
this model, `bytes_per_element` includes every required read and write, and each
counted vector operation must complete one useful update in every lane:

```text
rate = min(memory_bytes_per_second / bytes_per_element,
           cycles_per_second * vector_operations_per_cycle * lanes_per_vector)
```

For an illustrative, non-measured case with 32 gigabytes per second (GB/s) and
eight bytes per element, memory caps the rate at four billion elements per
second. A four-lane path at an illustrative 3 gigahertz and two vector
operations per cycle has a 24-billion-elements-per-second compute bound, so
extra lanes cannot help until memory traffic changes.
[`roofline_elements_per_second`] evaluates this bound.

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
| Scalar | Tiny inputs, tails, and a production baseline fallback | Lane parallelism | More instructions for independent work; this experiment's x86 scalar probe requires FMA | Inputs are short or no vector path passes its gate |
| 128 bit | Portable fixed-width parallelism across these two architectures | Memory limits or dispatch overhead | Limited to two double lanes | It wins on the target mix or provides the simplest common path |
| 256 bit | Four double lanes with AVX2 on x86-64 | AVX-512-only operations | On affected Intel generations, clock policy depends on instruction class, width, and active-core count | It wins request-level measurements and controls code size |
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
`x = fused_multiply_add(multiplier, addend, x)`. The scalar check limits the
absolute checksum difference to
`64 × 2^-52 × max(1, |scalar checksum|)`.

[`experiment/run_experiment.py`](experiment/run_experiment.py) calls the
baseline mode A and the candidate mode B. It launches fresh processes in
four-process ABBA and BAAB blocks, so both modes occupy early and late positions.
For each block, the log contrast is the average logarithm of the two candidate
times minus the average logarithm of the two baseline times. One complete block
is one replication. A paired Student-t interval describes uncertainty across
the eight block contrasts. Exponentiating their mean gives the geometric
candidate-to-baseline ratio; exponentiating their standard deviation gives the
multiplicative standard-deviation factor. An A/A control assigns both labels to
the same mode and screens label and position imbalance.

[`experiment/run_host.sh`](experiment/run_host.sh) binds a Git archive to one
authorized Linux target, records the host and toolchain, runs Rust and C
correctness checks, captures generated code, executes the fixed schedule, and
runs the independent receipt validator. See [`rounds/01.md`](rounds/01.md) for
the acceptance contract. Final host records belong under [`measurements/`](measurements/).

## Evidence boundary

The timing interval covers between-block variation during one run window. The
primary timer covers only the fixed-work kernel after same-mode warmup. Linux
`perf stat` user-mode counters cover process startup, warmup, and the main kernel
because they surround the child process. The x86-64 run groups user-mode core
cycles with reference cycles when the model exposes both events. Reference
cycles are intended not to scale with clock frequency. The Arm run records
user-mode core cycles only.

Cycle-to-reference-cycle ratios can be consistent with an effective-clock
change on the tested x86 processor. Because the counter scope differs from the
main timer, the ratio is a diagnostic consistency check, not an independent
prediction. A frequency license is an internal processor classification used to
select an allowed power and clock range; this experiment cannot observe or
prove a license transition. Virtual-machine scheduling, thermal drift, and
shared-machine work can remain. Linux steal time counts intervals when a virtual
processor wanted to run but the hypervisor did not schedule it; intervals
shorter than that counter's resolution can remain invisible. A result names one
host, compiler, binary, input, logical-processor placement, recorded
simultaneous-multithreading topology, and run window. It is not an
instruction-set-wide claim.

## Selection guide

1. Keep a production-baseline scalar path as the oracle and fallback; the x86
   scalar path in this focused probe is narrower but still requires FMA.
2. Dispatch only after exact feature detection.
3. Inspect the generated loop for every deployed target.
4. Measure fixed request sizes with process-level, order-balanced replication.
5. Include startup, tails, and attributable follow-on work in the decision.
6. Separate memory-bound workloads from compute-bound workloads.
7. Remeasure by processor model, compiler, active-core count, and service mix.

Primary sources and their version boundaries are in
[`references.md`](references.md).

[`roofline_elements_per_second`]: src/lib.rs
[`PathCost`]: src/lib.rs
[`fixed_work_time_ns`]: src/lib.rs
[`break_even_elements`]: src/lib.rs
