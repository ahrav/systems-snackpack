# Constant-time systems programming

Three equality implementations separate functional correctness, throughput and
security evidence. `early` deliberately leaks mismatch position. `xor` is a
full-scan teaching reduction, with no constant-time compiler guarantee.
`reviewed` uses pinned subtle 2.6.1 with default features disabled.

Lengths and buffer addresses are public; only the equality result is released.
Do not use the handwritten candidates as authentication primitives.

```bash
cargo test -p constant-time-systems
python3 topics/068-constant-time-systems/scripts/run.py /tmp/topic68-results
```

The runner requires a new output directory outside the repository, Cargo,
Python 3 and (on Linux) taskset, objdump, nm and lscpu. It builds an isolated
workspace using the pinned experiment.lock, records input hashes before Cargo,
and writes the build, binaries, disassembly and raw process samples under that
output directory. Network access or a Cargo cache is needed for
subtle 2.6.1. Rust 1.93 or newer is required by the workspace.

See [experiment](EXPERIMENT.md), [round notes](rounds/01.md),
[measurements](measurements/README.md), and [primary sources](references.md).
