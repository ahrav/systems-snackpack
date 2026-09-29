# Correctness evidence

Initial scratch runs passed on the required Arm host and runtime-resolved x86-64
`xxl`. Exact committed-source results and archive receipts follow in the retained
completion record. There is no measured proxy latency or throughput comparison.

Run the exact topic source on Linux with:

```bash
sh topics/062-load-balancing/scripts/run-linux.sh
```

The runner requires a workspace containing this topic, root Cargo manifest and
lockfile. It uses the host Rust toolchain, default target CPU, release optimization
level three, and no `RUSTFLAGS`. It writes host metadata, tests, model outputs,
optimized assembly, source hashes, and evidence hashes to ordinary scratch.
Do not commit those generated files into this repository.
