# Raw receipt layout

Keep full sealed receipts outside Git. Each host receipt contains source and
host identity, the archived source, build and code-generation output, every
semantic case, the checksum and reflink controls, a content manifest, and a
read-only seal.

Before deleting a remote receipt:

1. retrieve it without changing its files;
2. validate its exact expected source and host identity;
3. archive it and record the archive SHA-256;
4. retain it in the curriculum evidence directory;
5. remove only the task-owned exact remote paths.

A tree without both `MANIFEST.sha256` and `SEALED` is incomplete. Do not accept
an exit status or a self-reported `pass` field in place of independent
validation.
