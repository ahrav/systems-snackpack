# Immutable shared buffers with memfd sealing

[Lesson](rounds/01.md) | [Results](RESULTS.md) | [Sources](SOURCES.md)

```sh
cargo +1.93.1 test -p memfd-sealing
python3 topics/107-memfd-sealing/example.py
python3 topics/107-memfd-sealing/check.py
```

Run from the repository root. Python native checks require Linux. The Rust
range and seal-policy checks run on macOS and Linux. The example uses descriptor
inheritance after sealing for cross-process publication.
