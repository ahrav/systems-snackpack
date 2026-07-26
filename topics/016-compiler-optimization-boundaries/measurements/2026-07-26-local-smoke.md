# Local smoke run, 2026-07-26

Boundary:

- Apple arm64 host, Darwin kernel 25.5.0
- rustc 1.93.1, LLVM 21.1.8
- Cargo bench profile defaults
- one process, fixed local/imported/opaque order

Command:

```bash
cargo bench -p compiler-optimization-boundaries --bench boundary
```

Observed output:

```text
local_ns=2023416 checksum=486539170
imported_ns=2102208 checksum=486539170
opaque_ns=17267167 checksum=486539170
```

The equal checksums are a correctness smoke check. The timings are not a
comparative estimate: there is one process, no order balance, no independent
build replication, and no retained code-generation record for this run.
