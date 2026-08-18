# Exact-source binding

Both host archives were produced from final-reviewed source commit
`f43f0fe3766933e9f17ce4d0c7590345238dbbae` and one `git archive` with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`84f24c2ff91e38898d353481dd50b0effa66e25790eea433c736787e7a250802`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or Git reference (ref)
receipt, which would record the named reference and the commit it resolved to.
The pre-run remote-branch check is an observation by the controlling local
process, or orchestrator, outside these archives.

Each host recorded identical 1,796-entry pre/post source manifests. A source
manifest is a sorted inventory of file paths and their SHA-256 digests. The
manifest digest was
`374ac57fe934ba123f3c520ab41dca41d1e5a0c9281244315aaaacec20b8d6b4`.
The runner itself had digest
`1cf381d26693bc15fa554dde0aca173984866daad174e05411c968cc7938249c`.

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
