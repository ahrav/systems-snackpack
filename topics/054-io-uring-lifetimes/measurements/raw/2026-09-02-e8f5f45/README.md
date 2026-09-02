# Exact-source receipt bundle

This directory publishes compact evidence for the accepted Topic 54
correctness runs from source commit
`e8f5f459ae012e0b53867224bd6983aa50bd0cd6`.

- `source.txt` binds the source commit, path, archive, native source, and runner.
- `xxl-resolution.txt` records the runtime alias resolution.
- The external-result locators bind the retained read-only receipt directories
  and their manifest digests.
- The controller-validation JSON files record independent revalidation after
  retrieval and after copying into the evidence directory.
- `SHA256SUMS` binds every checked-in file in this directory except itself.

Each sealed receipt contains 17 files covered by `MANIFEST.sha256`, plus the
manifest and read-only `SEALED` marker. The covered files include exact source
and host identity, source inventories before and after execution, the native
binary, build output, assembly, disassembly, two process runs, and normalized
A/A controls.

The runs test four `io_uring` correctness contracts. They make no timing,
storage, `SQPOLL`, `IOPOLL`, registered-resource, multishot, provided-buffer,
seccomp, or Linux Security Module claim.
