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

A receipt validated before a validator change carries only the guarantees that
version checked. Revalidate the retained archive with the current validator
before citing it, extracting it so that its stored mode bits survive.

A receipt sealed before the launcher binding holds no `runner_sha256`, so the
current validator rejects it on that check. Such a receipt cannot establish which
launcher produced it; that provenance rests on the controller procedure until the
measurement is collected again.
