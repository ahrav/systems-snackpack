# Validation

All six repository checks passed with Rust 1.93.1:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace --lib --bins --examples
cargo test --workspace --doc
cargo bench --workspace --no-run
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
```

Workspace tests: 535 passed. Doctests: 153 passed. Topic tests: three unit tests
and one doctest on each of macOS arm64, Linux aarch64 and Linux x86_64.
Independent oracle: 55,987 comparisons on each host. Measured V8 processes:
36 per measured host, 72 total, plus three separate trace processes per host.
JavaScript syntax, Python compilation, writing policy, and full-branch whitespace
checks pass. Both Linux host logs hash `src/lib.rs`, `experiment/oracle.py`,
`experiment/run.py` and `experiment/bench.js`; the exported source archive and
`evidence/source-parity.json` cover those four plus `Cargo.toml` and
`examples/probe.rs`. All six digests are the measured bytes at source commit
ce874cce601335b4f0e7295ab3c7f23d8d61fff3. Review follow-ups after that commit
changed only `experiment/oracle.py` and `experiment/run.py` failure handling:
checks raise `SystemExit` so they hold under `python -O`, the oracle inherits the
probe's stderr, the runner removes inherited `NODE_OPTIONS` from both modes and
requires a fresh output directory. `src/lib.rs`, `examples/probe.rs`,
`experiment/bench.js` and `Cargo.toml` keep their recorded hashes, so every
measured process ran the committed benchmark and implementation bytes.

Standalone evidence retains complete gate logs; evidence/gate-log-hashes.json
records their SHA-256 digests. The Arm Node runtime remains unavailable as
described in results.md. Existing Git hooks and platform controls were preserved.
