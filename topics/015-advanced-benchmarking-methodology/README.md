# Advanced benchmarking methodology

The independent assignment sets the sample size. Inner timings are subsamples,
not process or build replicates.

For build `b`, process `p`, and inner iteration `i`, use the hierarchy:

```text
Y[b,p,i] = mean + treatment + build[b] + process[b,p] + residual[b,p,i]
```

Under a balanced independent random-effects model:

```text
Var(mean) =
    build_variance / builds
  + process_variance / (builds * processes)
  + iteration_variance / (builds * processes * iterations)
```

Extra inner iterations reduce only the last term. Use fresh processes when
runtime state varies. Use independent builds when the claim includes compiler
or layout variation.

## Compare variants inside short blocks

Put every variant in each block. For two variants, balance `AB` and `BA`
orders, then analyze one contrast per block. This prevents either label from
owning the first or second position.

The focused experiment is an A/A negative control. Labels `A` and `B` call the
same `checksum` function. Each block contains one fresh `AB` process and one
fresh `BA` process. The blockwise order-cancelled ratio is:

```text
sqrt((A/B in the AB process) * (A/B in the BA process))
```

A fixed order can name opposite winners when the second position inherits
cache or machine state. Identical labels under a reciprocal multiplicative
position effect cancel to `1`. A large residual rejects the measurement design
before it judges an optimization.

## Run the experiment

```bash
cargo build --release \
  -p advanced-benchmarking-methodology \
  --example order_bias

topics/015-advanced-benchmarking-methodology/experiment/run_processes.sh \
  target/release/examples/order_bias \
  /tmp/topic15-raw.csv \
  /tmp/topic15-summary.csv
```

On Linux, the runner uses `taskset -c 0` when `taskset` is available. Affinity
limits eligible CPUs; it does not isolate the CPU from interrupts or other
work. Record which runner branch executed when affinity is part of the claim.

The timer includes only the checksum calls. Process startup, allocation,
initialization, and the eviction-buffer traversal remain outside the timed
regions. Preserve the raw process rows and inspect the exact linked binary.

See the [measurement contract](measurements/README.md),
[cross-host record](measurements/2026-07-25-cross-host.md),
[first round](rounds/01.md), and [primary sources](references.md).
