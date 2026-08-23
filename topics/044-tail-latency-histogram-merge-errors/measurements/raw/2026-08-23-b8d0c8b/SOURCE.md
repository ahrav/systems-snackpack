# Scoped source identity

The checked-source run used Git commit
`b8d0c8b06bd29dab090d40f18aa6aa086b5fdf76`.

The retained `source.tar.gz` is a Git archive that contains the root build
contract and Topic 44 only:

- `.gitignore`
- `Cargo.lock`
- `Cargo.toml`
- `DOCUMENTATION.md`
- `README.md`
- `rust-toolchain.toml`
- `topics/044-tail-latency-histogram-merge-errors/`

This scope excluded historical artifacts from unrelated topics. Git embedded
the full source commit in the archive's global header. On each host, the
validator recomputed every archived file digest and matched it to the source
manifests recorded before and after execution.

The evidence-only change that adds these measurement notes and sealed bundles
does not change the Rust source, expected output, runner, or validator that this
archive contains.
