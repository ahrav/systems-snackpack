# Topic 7: Branchless code and predictable control flow

A branch speculates control. A conditional select creates a data dependency.
Choose between them from measured total cost, not source syntax or outcome
frequency alone.

## Cost model

Use this model to form a benchmark hypothesis:

```text
branch exposure
    ~= chosen path + site miss ratio * effective recovery cost

select exposure
    ~= candidate work + condition-to-result dependency + resource pressure
```

The terms overlap. A select deserves testing when both values are already legal
and cheap and the site is hard to predict. Retain the branch when one path is
rare, expensive, fault-sensitive, or useful for speculative memory overlap.

A 50/50 marginal distribution does not establish unpredictability. Alternating
outcomes carry history that a predictor can learn. Fixed-seed random outcomes
provide a different control even when their true fraction is also near 50%.

## Semantic boundary

Rust `if` evaluates only the selected block. `select_unpredictable` receives
already-evaluated values. Do not use it to guard a panic, fault, side effect, or
expensive call.

The portable [`std::hint::select_unpredictable`] API is a compiler hint. It does
not guarantee `cmov` or `csel`. The experiment instead fixes one machine-level
decision with register-only inline assembly. Both kernels use the same Rust
loop, but the compiler still controls surrounding loop shape. Inspect the
linked binary before interpreting a timing result. This control does not
represent the compiler's normal if-conversion policy.

## Run

Check equivalence:

```bash
cargo run -p systems-snackpack-topic-007 --example check_equivalence
cargo bench -p systems-snackpack-topic-007 --bench control_flow -- --verify
```

Run 12 balanced process pairs per outcome pattern on Linux:

```bash
topics/007-branchless-predictable-control-flow/experiment/run_processes.sh \
  /tmp/systems-snackpack-topic-007
cat /tmp/systems-snackpack-topic-007/summary.txt
```

The runner selects the first CPU allowed by its affinity mask unless `CPU` is
set. It crosses all six pattern orders with both branch/select orders. Each
process constructs one buffer, checks both kernels, warms the selected kernel,
then times one non-inlined call.

The summary validates the session, pair, process, input, and order metadata
before treating fresh processes as replication units. Under independent,
identically distributed continuous pair ratios, the exact 96.1% interval for
the paired median is the third through tenth ordered ratio from 12 pairs. It
covers process-run variation in one host window under those assumptions, not
input, build, machine, or fleet variation.

## Measured result

Commit `26b49a5` ran on both required Linux hosts with Rust 1.93.1, native CPU
features, vectorization disabled, 12 order-balanced process pairs per pattern,
and 100,663,296 decisions per timed process. Ratios above one favor select.

| Host | Zeros | Alternating | Fixed random |
| --- | ---: | ---: | ---: |
| AArch64 host | 1.066 | 1.240 | 4.846 |
| x86-64 host | 1.380 | 1.083 | 8.403 |

These paired geometric means apply only to the recorded binaries, hosts, and
run windows. The random penalty is consistent with recovery from wrong-path
speculation, but no site-attributed miss counter was measured. See the
[cross-host record](measurements/2026-07-17-cross-host.md) for intervals,
dispersion, code generation, and startup boundaries.

See [Round 1](rounds/01.md), [measurement records](measurements/README.md), and
[source scopes](references.md).

[`std::hint::select_unpredictable`]: https://doc.rust-lang.org/stable/std/hint/fn.select_unpredictable.html
