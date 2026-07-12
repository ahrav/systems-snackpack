# Systems Snackpack

Executable notes from an advanced systems curriculum.

Each topic is a Rust crate. The crate contains code, tests, benchmarks, concise
references, and round notes. It does not store lesson transcripts.

## Run the workspace

```bash
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo bench --workspace --no-run
```

## Repository rules

- Topic numbers stay fixed at 1 through 83.
- A revisit adds a new round inside the existing topic crate.
- Public Rust APIs carry rustdoc. Doctests, tests, and benchmark programs must compile.
- Measurement notes name the machine, toolchain, flags, input, and result.

See [documentation rules](DOCUMENTATION.md) for the writing and verification gate.
