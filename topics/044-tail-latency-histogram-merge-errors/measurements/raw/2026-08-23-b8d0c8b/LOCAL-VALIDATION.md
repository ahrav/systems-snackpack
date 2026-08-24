# Local validation

Date: 2026-08-23

The source commit passed:

```text
git diff --check
cargo fmt --all -- --check
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo clippy --workspace --all-targets -- -D warnings
cargo bench --workspace --no-run
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps
```

The focused package passed five tests, the release example printed
`status=PASS`, and eight local fresh processes matched `experiment/expected.txt`.
`bash -n` accepted the host runner, and both Python scripts passed syntax
compilation. A fresh documentation writer pass was followed by an isolated
fact and mechanical verifier. The verifier's linked-symbol and receipt-integrity
findings were fixed, then the focused re-verification passed.

After retrieval, the checked-in validator independently accepted the Arm and
`xxl` bundles with their exact target labels and resolved hostnames.

No timing benchmark was run because this round makes no elapsed-time claim.
