# Retained receipt layout

Full sealed receipts stay outside Git under the curriculum evidence directory.
Each receipt contains the exact topic archive, provenance, host inventory,
build and model checks, code-generation records, route snapshots, the complete
24-period bidirectional campaign, and a content manifest.

Before removing remote scratch:

1. Retrieve both receipts while preserving modes.
2. Validate each receipt against the expected commit, archive hash, host, and
   architecture.
3. Archive the validated receipt and record its SHA-256 and manifest digest.
4. Store those archives in the retained Topic 55 evidence directory.
5. Remove only the exact task-owned remote paths.

Git stores compact controller-validation results, external archive locators,
source identity, runtime `xxl` resolution, and hashes of those compact files.
It does not store the full receipts.

Accepted bundles:

- [`2026-09-04-d20ee11`](2026-09-04-d20ee11/README.md)
