# Documentation rules

Write the code first. Then document the facts a reader cannot recover from the
signature or implementation.

- Public Rust APIs carry rustdoc. Unsafe code states its safety contract.
- Module docs explain the purpose, invariant, and runnable entry point.
- Comments explain constraints and decisions. They do not narrate code.
- Examples compile as doctests, examples, or benchmark programs.
- Measurements name the CPU, operating system, toolchain, flags, input, trial count, and result.
- Markdown uses short sentences, active voice, and direct claims. Do not use filler, hedging, or promotional language.

Before merge, run:

```bash
cargo fmt --all -- --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo bench --workspace --no-run
RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps
```

`missing_docs = "deny"` enforces public rustdoc coverage. Rustdoc and doctests
verify links and examples. A fresh documentation review verifies prose claims
against the code before substantial documentation changes merge.
