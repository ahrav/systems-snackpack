# Local and host validation

## Local workspace

Host: Apple arm64, Darwin `25.6.0`. Toolchain: `rustc 1.93.1`, LLVM `21.1.8`,
`cargo 1.93.1`, Python `3.14.5`, and ShellCheck `0.11.0`.

All commands passed on 2026-08-25:

```text
git diff --check
cargo fmt --all -- --check
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo clippy --workspace --all-targets -- -D warnings
cargo bench --workspace --no-run
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps
bash -n topics/046-cache-coherence-false-sharing/experiment/run_host.sh
shellcheck topics/046-cache-coherence-false-sharing/experiment/run_host.sh
python3 -I -B -c '<compile both Topic 46 Python scripts>'
sha256sum -c topics/046-cache-coherence-false-sharing/measurements/raw/2026-08-25-e4fb542f/SHA256SUMS
```

A deterministic fake probe exercised two primary and two A/A blocks in
`run_processes.py`. It retained 16 valid attempts, recovered the injected
packed/padded ratio of 2.0, recovered an A/A ratio of 1.0, and kept the runner
and fake-binary hashes unchanged.

The independent `doc-rigor` writer changed Rust comments only. A fresh verifier
checked function contracts, layout, cfg and FFI boundaries, unsafe comments,
barrier timing, affinity validation, `Relaxed` semantics, evidence limits, and
the runnable command. Focused tests, doctests, and warning-denied rustdoc passed;
the verifier reported no findings.

## Source-bound Linux gates

Both hosts verified source commit
`e4fb542f6640566f8f7fbcd220eb1f52c388df04`, Git archive SHA-256
`f0b8c64c9cacfb27314ae7e4ac90102c6ec9709a03e4b2ded759209a3eb0385b`,
and the executing runner against the archived runner.

The Arm and `xxl` receipt validators each reported `PASS`: 48 attempts, eight
primary blocks, four A/A blocks, unchanged source manifests, unchanged runner
and binary hashes, passing library/example/doctests, correct field layouts and
counts, verified one-CPU affinity, and accepted architecture-specific code
generation.

After retrieval, both compressed bundle digests matched `SHA256SUMS`. A local
independent pass expanded each bundle and checked every file in its internal
evidence manifest except the deliberately omitted duplicate source archive.
Both receipt-validation documents and both process summaries reported `PASS`
with no invalid attempts.
