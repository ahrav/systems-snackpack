# Immutable shared buffers with memfd sealing

[Lesson](rounds/01.md) | [Results](RESULTS.md) | [Sources](SOURCES.md)

```sh
cargo +1.93.1 test -p memfd-sealing
python3 topics/107-memfd-sealing/example.py
python3 topics/107-memfd-sealing/check.py
```

Run from the repository root. Python native checks require Linux. The Rust
range and seal-policy checks run on macOS and Linux. The example performs both
roles in one process. The checker publishes across processes by descriptor
inheritance after sealing.

The checker requires a kernel with `F_SEAL_FUTURE_WRITE`, which mainline Linux
provides from 5.1, and Python 3.8 or later with assertions enabled, the
`python3` default. It validates with `assert`. A run under `python3 -O` or
`PYTHONOPTIMIZE=1` exits with status 1 before it prints the `PASS` record.
