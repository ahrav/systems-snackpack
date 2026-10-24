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
its closed-form oracle. Each host's `hashes.txt` recorded the source and script
digests of commit 6c20563db07c983155ba4c7bb6247d92bbda9d7a at measurement time.
`src/lib.rs` and `src/main.rs` still match those digests. Review commits after
measurement change `run.py`, `build.sh`, `analyze.py` and `oracle.py` as listed in
results.md, so their current digests differ; `build.sh` keeps the measured toolchain
pin and compiler flags, and `scripts/test_*.py` exercise the changed scripts.

CPU0..7 are eight distinct visible cores in one NUMA node on each host; topology.txt
under arm/ and xxl/ records the core, socket and node of each CPU. Affinity
is inherited by worker threads; the kernel can migrate them inside that set.
Host/toolchain metadata, raw CSV, all process attempts, source hashes and analysis
are retained under arm/ and xxl/. The complete source archive and executable images
are retained with the automation evidence outside the repository.

Both rendered figures were inspected; `scripts/scan_figure.py` draws scan.svg and
scan.png. The standalone demo passed. The downloadable bundle includes the topic and
minimal workspace metadata for Cargo reproduction.
The experiment is descriptive and scoped to warm calls with thread spawn/join.
See results.md for variability, pair decisions, measured-versus-inferred limits.
