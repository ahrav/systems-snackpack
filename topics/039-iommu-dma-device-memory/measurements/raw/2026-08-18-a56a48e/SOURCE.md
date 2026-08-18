# Exact-source binding

Both host archives were produced from the post-review source commit
`a56a48e32d78ee942163c66c25a9661e9b75fa52` and one `git archive` with Secure
Hash Algorithm 256-bit (SHA-256) digest, a content fingerprint,
`33e08d63e7c439742d7a8acb103f2d1fcc2d19e0b667d809de93a992aec5aa9f`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or Git reference (ref)
receipt, which would record the named reference and the commit it resolved to.
The pre-run remote-branch check is an observation by the controlling local
process, or orchestrator, outside these archives.

Each host recorded identical 1,796-entry pre/post source manifests. A source
manifest is a sorted inventory of file paths and their SHA-256 digests. The
manifest digest was
`01e3d0283154a01deda3595684372984428d18dd6af66adc89280ece89519f10`.
The runner itself had digest
`5fa08181b4ebfbcae12a9f26e17df21e46304656e71b1e2790e8c287eb44d2e9`.

Repository history must verify that the later evidence-only commit adds only
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
