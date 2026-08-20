# Source and receipt identity

- Source commit: `f32d0dbfcc146bc0fb2d8739c2da668a95d95bd9`
- Git archive SHA-256: `c93c116e1e0db312c0a85b9a34a65180b2c0df50d85f3e04943ad768c7d48231`
- C probe SHA-256: `faab623812e641585f0c4fa56fd74f9801faa4dde84f4d20431a0a3eb72cf8e8`
- Arm archive: `arm-results.tar.gz`
- `xxl` archive: `xxl-results.tar.gz`
- Local receipt validation: both archives passed
  `experiment/validate_receipts.py` after retrieval.
- Measurement boundary: correctness and generated-code inspection only; no
  timing claim.

The Git archive itself is not retained because it contains the full repository
tree snapshot and is much larger than the focused receipts. Each host bundle
retains its archive digest, embedded commit identity, source manifest, exact C
source, contract, runner, validator, built executable, and execution evidence.
