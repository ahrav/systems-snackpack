# Raw host archives

Each promoted archive contains one required host's exact-source build,
correctness receipts, independent validation, generated-code inspection,
workspace gates, host identity, tool provenance, and internal checksum
manifest. The parent commit directory contains an outer Secure Hash Algorithm
256-bit (SHA-256) checksum file named `SHA256SUMS`.

Do not treat a raw archive as current evidence after source changes. The host
and comparison notes bind each archive to one source commit and source-archive
digest.

Promoted archives may omit a redundant full-repository source payload when its
digest, exact commit, before/after source manifests, and an explicit omission
record remain in the archive. Per-process and validation receipts must not be
removed.
