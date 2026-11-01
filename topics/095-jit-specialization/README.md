# JIT specialization and recovery

The Rust model specializes layout A and a signed 32-bit sum. Both guards precede
an item's committed effect. Failure preserves the prefix and resumes the baseline
at the failing item. The result records the ordered effect sequence.

From the repository root:

```bash
cargo test -p topic095-jit-specialization
cargo build --release -p topic095-jit-specialization --example probe
python3 topics/095-jit-specialization/experiment/oracle.py
python3 topics/095-jit-specialization/experiment/run.py --out /tmp/jit-results
node --trace-opt --trace-deopt topics/095-jit-specialization/experiment/bench.js shift
```

The Python oracle enumerates 55,987 short arrays using exact integer sums and
expected effect sequences. The separate JavaScript experiment compares Node's
default V8 configuration with `--jitless` across stable, changed, and alternating
object layouts. Supply `--node /absolute/path/to/node` when needed.

See [results](results.md) for workloads, controls, all sample ranges, host
identities, source identity, trace findings, and the missing Arm Node run.
See [sources](sources.md) for runtime mechanics and correctness references.
