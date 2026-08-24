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

The checked-in tree has since diverged from this sealed archive: review fixes
changed `src/lib.rs` (large-count quantile arithmetic, cumulative-counter
validation, and total-count enforcement on record and merge),
`experiment/run_processes.py`, `experiment/validate_receipts.py`, and
`experiment/run_host.sh` (its self-validation now passes `--host-run`).
`experiment/expected.txt` is unchanged and the current release probe still
prints byte-identical output. These receipts remain evidence for the archived
`b8d0c8b` revision only; the newer code paths are covered by the package's
unit tests, not by these bundles.
