# Futex fast paths, parking behavior, and wakeup storms

Compare a spin-only lock, immediate parking with wake-one, immediate parking with
wake-all, and 100 spin iterations followed by wake-one parking. The 0/1/2 state
machine keeps an obligation to wake on contended release. It does not promise
FIFO service, bounded starvation, priority inheritance, cancellation, or recovery
after owner death. Use established mutex libraries for production.

The guarded payload and exclusion sentinel are atomic. Exclusion defects cannot
create a non-atomic payload data race. Finite aggregate checks can miss defects.
Passing these tests
does not prove arbitrary non-atomic payload or lifetime soundness.

From the repository root, on Linux AArch64 or x86-64 with 64-bit pointers
(x32 is excluded):

```sh
cargo test -p futex-parking --lib
cargo test -p futex-parking --doc
RUSTFLAGS='-C target-cpu=native' cargo build -p futex-parking --release --example compare
python3 topics/069-futex-parking/scripts/run.py "$PWD/target/release/examples/compare" results
python3 topics/069-futex-parking/scripts/summarize.py results/runs.jsonl results/summary.json
```

The runner requires at least four available logical CPUs. macOS checks portable
code and documents; the example exits unsupported rather than simulating futexes.

Read [the controls](EXPERIMENT.md), [results](measurements/README.md), and
[primary sources](references.md).
