# Exact-source receipt bundle

Both accepted receipts bind source commit
`8ad95023e53c516499c1c85631582c52ebd63921` to archive SHA-256
`1c8669600b7c28645ee50242c0934d2d5ec1110afd98e360d757bc636dd095ef`.
Fresh controller extraction and validation passed for each archive.

- `arm-retry2-results.tar.gz`: accepted 64-process Arm retry.
- `xxl-results.tar.gz`: accepted 64-process runtime-resolved x86 campaign.
- `arm-rejected-first-campaign.tar.gz`: preserved fixed-horizon Arm campaign
  rejected after attempt 64 failed canaries; its estimates are unused.
- `*-controller-validation.json`: validation using controller-held host and
  source expectations.
- `xxl-resolution.txt`: alias resolution and runtime identity for this run.
- `source.txt`: shared source identity and campaign boundary.
- `SHA256SUMS`: outer publication hashes.

The accepted bundles contain every raw process result, linked binary and
disassembly, host metadata, analysis, and inner seal. The outer archives are
small because the receipt stores text evidence and compressed binaries, not
the allocated benchmark working sets.
