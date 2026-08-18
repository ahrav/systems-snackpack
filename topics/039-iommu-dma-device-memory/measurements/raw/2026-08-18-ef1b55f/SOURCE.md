# Exact-source binding

Both host archives were produced from final-reviewed source commit
`ef1b55f3cc2b9924e46de035d1f1b2e02e07bb08` and one `git archive` with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`6df35758b2d84a192c2a1470bd6e75a198865d4b3d1cefa67ec3635783585403`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or Git reference (ref)
receipt, which would record the named reference and the commit it resolved to.
The pre-run remote-branch check is an observation by the controlling local
process, or orchestrator, outside these archives.

Each host recorded identical 1,796-entry pre/post source manifests. A source
manifest is a sorted inventory of file paths and their SHA-256 digests. The
manifest digest was
`ed776a724e324ffd6ffdc511c6d04002c15f08f4ddf152cb7819907a9e7faef1`.
The runner itself had digest
`baaecdc0fcacadeb9bd1edbc75a62c76d7cf5eac7f1f37682c273f1a85b8c3d3`.

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
