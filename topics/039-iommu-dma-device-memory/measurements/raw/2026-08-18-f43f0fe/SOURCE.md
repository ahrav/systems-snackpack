# Exact-source binding

Both host archives were produced from final-reviewed source commit
`f43f0fe3766933e9f17ce4d0c7590345238dbbae` and one `git archive` with SHA-256
digest `84f24c2ff91e38898d353481dd50b0effa66e25790eea433c736787e7a250802`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or ref receipt; the
pre-run remote-branch check is an orchestrator observation outside these
archives.

Each host recorded identical 1,796-entry pre/post source manifests with digest
`374ac57fe934ba123f3c520ab41dca41d1e5a0c9281244315aaaacec20b8d6b4`.
The runner itself had digest
`1cf381d26693bc15fa554dde0aca173984866daad174e05411c968cc7938249c`.

Repository history must verify that later evidence-only commits add only
archives and summaries; the host bundles cannot prove that claim.

Verify the retrieved archives with:

```bash
shasum -a 256 -c SHA256SUMS
```

After extracting either archive, change into its result directory and run:

```bash
shasum -a 256 -c MANIFEST.sha256
```

Both 76-entry internal manifests passed after retrieval. The raw archives
contain host metadata, toolchain and target-feature records, package gates,
all 16 process streams and identities, source manifests, linked symbols,
relocations, complete disassembly, validation output, and completion status.
The local validator also rechecked both extracted process trees against the
checked-in expected output.
