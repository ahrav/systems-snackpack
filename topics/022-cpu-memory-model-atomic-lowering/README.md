# CPU memory model and Rust atomic lowering

Atomics create language-level ordering edges. They do not flush caches. Prove
the required happens-before path first, then inspect the exact lowering.

## Model

Each atomic location has its own modification order. A Release operation
synchronizes with an Acquire operation only when the acquire reads the release
or its C++20 release sequence. `SeqCst` adds one order over sequentially
consistent operations; it does not turn weaker accesses into a transaction.

The generated instruction depends on rustc, LLVM, target, features, width, ABI,
and flags. Identical x86 instructions can retain different compiler-ordering
semantics. AArch64 can select RCpc, RCsc, LSE, LL/SC, or outline-helper paths.

## Cost model

```text
atomic cost = access + order encoding + lost overlap + coherence ownership
            + retry + queueing + helper dispatch
```

Contention and ownership transfer can dominate the ordering suffix. A Relaxed
RMW still serializes in one modification order. SeqCst can match AcqRel for an
RMW while differing sharply for a store.

## Run

```bash
cargo test -p cpu-memory-model-atomic-lowering
cargo run --release -p cpu-memory-model-atomic-lowering --example publication
cargo run --release -p cpu-memory-model-atomic-lowering --bin store-buffering -- relaxed 1000000 0 1 2
cargo build --release -p cpu-memory-model-atomic-lowering --bin atomic-cost
python3 topics/022-cpu-memory-model-atomic-lowering/experiment/run_processes.py \
  target/release/atomic-cost /tmp/topic22-processes
```

See [the experiment contract](experiment/README.md), [measurement records](measurements/README.md),
and [primary sources](references.md).

The exact-source two-host run found a 33.987× SeqCst/Release store ratio on the
recorded `xxl` host, where final code used `xchgq` versus `movq`. The recorded
Arm host used `STLR` for both and measured a 0.999962 ratio. SeqCst/Relaxed
private-line RMW ratios were 0.999307 and 1.001299, respectively. These results
apply only to the recorded hosts, toolchains, binaries, and workload.
