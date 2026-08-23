# Source and receipt identity

- Source commit: `af126fa920f51969667e02b926786cca598212ea`
- Pushed branch: `curriculum/topic-042-rust-aliasing-provenance`
- Git archive SHA-256: `f83290e6f41ec6c704cd61f2033bae1f90e749dbd2799137172a7ab322e99b7d`
- Embedded Git archive commit:
  `af126fa920f51969667e02b926786cca598212ea`
- Host runner SHA-256:
  `550bd4035464c4e9d326b8451d1469f97eb5efc9d195d6970d682450aa19c408`
- Source manifest SHA-256 (identical in both host bundles):
  `b6ba0132715ce3e3ea81f373664c50bc34c7babe2ec4c616601137654af659d1`
- Arm archive: `arm-results.tar.gz`
- `xxl` archive: `xxl-results.tar.gz`
- Final local gate archive: `local-validation.tar.gz`
- Local receipt validation on 2026-08-21: both extracted archives passed every
  entry in `bundle-manifest.sha256` and
  `experiment/validate_receipts.py` after retrieval.
- Measurement boundary: deterministic correctness and generated-code
  inspection only; no timing claim.

## Harness boundary for this evidence

These bundles were produced by host runner `550bd403…`, before the harness was
hardened to require privileged Bash, refuse `LD_PRELOAD` and `LD_AUDIT`, sweep
`RUSTUP_TOOLCHAIN`, assert the archive's toolchain pin against the resolved
`rustc` and `cargo`, isolate `CARGO_HOME`, and resolve `HOME` from the password
database. Those protections constrain later runs and cannot be applied
retroactively: re-validating these bundles checks their recorded identity and
internal consistency, not the ambient inputs present when they were produced.
Raising this evidence to the hardened boundary requires a fresh run of the
current runner on both named hosts.

The Git archive is not retained because it contains the full workspace,
including earlier topics' raw evidence. Each host bundle retains the archive
digest, embedded commit identity, full extracted-source manifest, runner
identity, host and toolchain records, workspace gates, built executable, eight
process streams, code-generation files, and bundle digest manifest.
