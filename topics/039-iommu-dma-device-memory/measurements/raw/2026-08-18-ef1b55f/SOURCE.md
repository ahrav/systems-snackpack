# Exact-source binding

Both host archives were produced from final-reviewed source commit
`ef1b55f3cc2b9924e46de035d1f1b2e02e07bb08` and one `git archive` with SHA-256
digest `6df35758b2d84a192c2a1470bd6e75a198865d4b3d1cefa67ec3635783585403`.
The runner verified the archive's embedded Git commit and digest before
extraction. The host bundles do not contain a branch or ref receipt; the
pre-run remote-branch check is an orchestrator observation outside these
archives.

Each host recorded identical 1,796-entry pre/post source manifests with digest
`ed776a724e324ffd6ffdc511c6d04002c15f08f4ddf152cb7819907a9e7faef1`.
The runner itself had digest
`baaecdc0fcacadeb9bd1edbc75a62c76d7cf5eac7f1f37682c273f1a85b8c3d3`.

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
