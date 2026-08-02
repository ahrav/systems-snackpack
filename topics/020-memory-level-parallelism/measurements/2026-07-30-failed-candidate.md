# Rejected source candidate: 2026-07-30

Commit `211f8b83db5476a6924726ddb173b9fff3ba0639` and archive SHA-256
`c732570be6a5bf66b9b615e600181819f75d26ad16735f539371d0d1af2aa197`
were attempted on both live machines.

Both wrappers exited 141 before source-manifest collection. With `pipefail`
enabled, gzip received SIGPIPE after `git get-tar-commit-id` stopped reading
the decompression stream. The embedded commit itself was correct. No workspace
gate, correctness result, code-generation result, or timing from this candidate
was accepted.

Commit `635f8687466c12889a33b6ae7900b0535a1480c1` fixed the verifier by fully
decompressing the archive before extracting the commit ID. Both subsequent
runs passed.

The sealed failure records are under
[`raw/211f8b8-failed`](raw/211f8b8-failed).
