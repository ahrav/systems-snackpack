# Exact-source binding

Both host archives were produced from final-reviewed source commit
`068d082c422efce23700949b01af80f3f2554572` and one `git archive` with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`f34a828911083552792785c5ebe751f83efc25885489e895be9de3c44a6c9dc7`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or Git reference (ref)
receipt, which would record the named reference and the commit it resolved to.
The pre-run remote-branch check is an observation by the controlling local
process, or orchestrator, outside these archives.

Each host recorded identical 1,796-entry pre/post source manifests. A source
manifest is a sorted inventory of file paths and their SHA-256 digests. The
manifest digest was
`1750399952b21e1470ba42a1574c7ff3679feb216917b6627ee0870fd6591c92`.
The runner itself had digest
`8243ff45cd0774f73addc4e82a06b20d3acc88504531dea051239a4322f7f2c1`.

Repository history must verify that later evidence-only commits add only
archives and summaries; the host bundles cannot prove that claim.

Verify the retrieved archives against the outer checksum-list file, literally
named `SHA256SUMS`, with:

```bash
shasum -a 256 -c SHA256SUMS
```

After extracting either archive, change into its result directory and verify
the internal manifest file, literally named `MANIFEST.sha256`, with:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Both 76-entry internal manifests passed after retrieval. The raw archives
contain host metadata; toolchain versions; target-feature records listing
compiler-reported instruction capabilities; package-gate results from format,
test, lint, documentation, and build commands; and the standard output,
standard error, exit status, and executable identity for all 16 processes. They
also contain source manifests, linked symbol records that identify named
functions, relocation records that show linker fixups used to resolve calls,
complete disassembly that renders generated machine instructions as text,
validation output, and completion status. The local validator also rechecked
both extracted directories of per-process records against the checked-in
expected output.
