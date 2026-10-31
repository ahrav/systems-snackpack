# Validation

All six repository gates passed on macOS with Rust 1.93.1:

- `cargo fmt --all -- --check`
- `cargo clippy --workspace --all-targets -- -D warnings`
- `cargo test --workspace --lib --bins --examples`: 532 tests passed.
- `cargo test --workspace --doc`: 152 doctests passed.
- `cargo bench --workspace --no-run`
- `RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps`

Local and both required Linux hosts passed three topic unit tests, one doctest,
333,504 independent oracle comparisons and all workload count checks using exact
committed implementation and harness bytes. The broken no-barrier control fails
the intended preservation condition in its unit test. Final source files match
local replay bytes and recorded remote hashes.

Writing-policy and full-branch whitespace checks passed. An initial Clippy
collapsible-if finding was fixed before final committed-source runs. Preliminary
wrong-directory Cargo commands failed before execution; local sysctl identification
was denied before measurement and its log is retained. Final campaigns completed.
Raw full-workspace logs are retained with the standalone lesson in outputs.
