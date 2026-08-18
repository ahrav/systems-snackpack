# Exact-source binding

Both host archives were produced from final-reviewed source commit
`2bb0d3e55efda225caeaeafbb285382824692b64` and one `git archive` with SHA-256
digest `e5711fbfada35934afb39e4c3492f62a3066b731c05981d35c8dce0d7e31f614`.
The runner copied that archive into a private work area, then verified the
snapshot's embedded Git commit and digest before extraction. The host bundles
do not contain a branch or ref receipt; the pre-run remote-branch check is an
orchestrator observation outside these archives.

Each host recorded identical 1,796-entry pre/post source manifests with digest
`8ef24be5277b91e4975e5fcd1fd41b2a996e9476e8cc253d6a6ed2629c245fa4`.
The runner itself had digest
`0578a461a9b44448eea32fbe5b2839bb0723b03bd7a654d75c3765b28624be1a`.

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
