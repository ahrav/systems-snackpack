# Local validation

The source candidate passed:

```text
git diff --check
cargo fmt --all -- --check
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo test --workspace --lib --bins --examples
cargo clippy --workspace --all-targets -- -D warnings
cargo bench --workspace --no-run
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps
```

The Topic 43 package was rerun after the final codegen-capture change with unit,
binary, documentation, formatting, and Clippy gates. Both Linux receipt
validators independently returned `status: pass`.
