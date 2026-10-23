# Validation

All six repository checks passed with Rust 1.93.1 on macOS:

- cargo fmt --all -- --check
- cargo clippy --workspace --all-targets -- -D warnings
- cargo test --workspace --lib --bins --examples
- cargo test --workspace --doc
- cargo bench --workspace --no-run
- RUSTDOCFLAGS="-D warnings" cargo doc --workspace --no-deps

Both declared Linux hosts compiled the exact committed source with Rust 1.93.1.
Each passed five unit tests, 378 independent arbitrary-precision oracle cases and
162 measured processes, plus two A/A processes. Every final benchmark output passed
its closed-form oracle. Source and script hashes match commit
6c20563db07c983155ba4c7bb6247d92bbda9d7a. The final publication adds only prose,
figures and retained measurements. Measured source and runner bytes are unchanged.

CPU0..7 are eight distinct visible cores in one NUMA node on each host. Affinity
is inherited by worker threads; the kernel can migrate them inside that set.
Host/toolchain metadata, raw CSV, all process attempts, source hashes and analysis
are retained under arm/ and xxl/. The complete source archive and executable images
are retained with the automation evidence outside the repository.

Both rendered figures were inspected. The standalone demo passed. The downloadable
bundle includes the topic and minimal workspace metadata for Cargo reproduction.
The experiment is descriptive and scoped to warm calls with thread spawn/join.
See results.md for variability, pair decisions, measured-versus-inferred limits.
