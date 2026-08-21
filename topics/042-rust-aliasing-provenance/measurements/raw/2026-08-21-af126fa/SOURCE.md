# Source and receipt identity

- Source commit: `af126fa920f51969667e02b926786cca598212ea`
- Pushed branch: `curriculum/topic-042-rust-aliasing-provenance`
- Git archive SHA-256: `f83290e6f41ec6c704cd61f2033bae1f90e749dbd2799137172a7ab322e99b7d`
- Embedded Git archive commit:
  `af126fa920f51969667e02b926786cca598212ea`
- Host runner SHA-256:
  `550bd4035464c4e9d326b8451d1469f97eb5efc9d195d6970d682450aa19c408`
- Arm archive: `arm-results.tar.gz`
- `xxl` archive: `xxl-results.tar.gz`
- Final local gate archive: `local-validation.tar.gz`
- Local receipt validation on 2026-08-21: both extracted archives passed every
  entry in `bundle-manifest.sha256` and
  `experiment/validate_receipts.py` after retrieval.
- Measurement boundary: deterministic correctness and generated-code
  inspection only; no timing claim.

The Git archive is not retained because it contains the full workspace,
including earlier topics' raw evidence. Each host bundle retains the archive
digest, embedded commit identity, full extracted-source manifest, runner
identity, host and toolchain records, workspace gates, built executable, eight
process streams, code-generation files, and bundle digest manifest.
