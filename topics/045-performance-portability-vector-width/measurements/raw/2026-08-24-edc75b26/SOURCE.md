# Scoped source identity

The checked-source run used Git commit
`edc75b260d1909bb9c4d043cbfadba5e98e38944`.

`source.tar.gz` is a Git archive with Secure Hash Algorithm 256-bit (SHA-256)
digest
`1c1f7c89a513ec6409367b3b5605def6748ba95d2a9f1a55fcfe67c111031852`.
It contains the root build contract and Topic 45 source as it existed at that
commit:

- `.gitignore`
- `Cargo.lock`
- `Cargo.toml`
- `DOCUMENTATION.md`
- `README.md`
- `rust-toolchain.toml`
- `topics/045-performance-portability-vector-width/`

Git embedded the full commit identifier in the archive. Each host verified the
archive digest and commit, compared its runner with the archived runner,
recorded every archived file digest before and after execution, and retained an
empty source-manifest diff.

The checked-in tree necessarily adds measurement notes and bundles, updates the
measurement indexes, and fills the round's retained-result paragraph after the
run. The benchmark, runner, receipt validator, generated-code checker, Rust
model, topic README, experiment README, and references used by the run are
byte-identical to the scoped archive.
