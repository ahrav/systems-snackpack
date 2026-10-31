# Validation

All six repository gates passed on macOS with Rust 1.93.1:

- `cargo fmt --all -- --check`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo test --workspace --lib --bins --examples`: 532 tests passed.
- `cargo test --workspace --doc`: 152 doctests passed.
- `cargo bench --workspace --no-run`
- `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`

Local and both required Linux hosts passed three topic unit tests, one doctest,
333,504 independent oracle comparisons and all workload count checks using the
implementation and harness bytes at `2b2da8b` (`evidence/*-source-hashes.txt`).
The broken no-barrier control fails the intended preservation condition in its
unit test. Source files at that commit match local replay bytes and recorded
remote hashes. Review follow-ups after it changed only `oracle.py` and
`measure.py` failure handling and CPU selection; `src/lib.rs` and
`examples/probe.rs` keep their recorded hashes.

Writing-policy and full-branch whitespace checks passed. An initial Clippy
collapsible-if finding was fixed before final committed-source runs. Preliminary
wrong-directory Cargo commands failed before execution; local sysctl identification
was denied before measurement and its log is retained. Final campaigns completed.
Raw full-workspace gate logs (`gate-1.log` through `gate-6.log`) are retained
with the standalone lesson outputs outside this repository; their digests are in
`evidence/raw-log-sha256.txt` alongside the committed host logs, so
`sha256sum -c --ignore-missing evidence/raw-log-sha256.txt` verifies the
committed files.
