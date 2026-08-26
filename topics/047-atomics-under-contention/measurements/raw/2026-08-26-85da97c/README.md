# Topic 47 raw receipts

These archives bind the final process results to source commit
`85da97ca0070461daf74a72586888903ea170e16` and source archive SHA-256
`6af2754b232eaed3c6296762f794882ea6cc7271aa8c561feef12af810245d3d`.
The sealed source archive excludes only unrelated Topics 1-46 raw measurement
directories; it includes the complete workspace source and Topic 47 artifact.

- `arm-results.tar.gz`: 2,627,995 bytes, 64 valid attempts.
- `xxl-results.tar.gz`: 2,737,138 bytes, 64 valid attempts.
- `SHA256SUMS`: outer archive digests.
- `source.txt`: source, branch, archive policy, and failed-preflight audit trail.
- `xxl-resolution.txt`: the local alias resolution immediately before the run.
- `host-model-probes.txt`: post-run processor-model probes.

Each result archive contains the sealed source, unchanged source manifests,
binary and runner hashes, source gates, smoke results, all raw attempts,
recomputed statistics, linked disassembly, symbol-address mapping, host data,
`receipt-validation.json`, and `status.txt`.
