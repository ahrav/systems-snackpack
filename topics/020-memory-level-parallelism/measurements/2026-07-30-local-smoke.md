# Local smoke: 2026-07-30

This run verifies that both treatments execute. Its fixed order and shared
process do not support a comparative performance claim.

| Boundary | Value |
|---|---|
| Host | `b0f1d8752aba` |
| OS | macOS 26.5.2, Darwin 25.5.0 |
| Architecture | `arm64` |
| Rust | rustc 1.93.1, LLVM 21.1.8 |
| Command | `TOPIC20_SMOKE_NODES=65536 TOPIC20_SMOKE_LOADS=1048576 cargo bench --locked --package memory-level-parallelism --bench chain_sweep` |
| Binary SHA-256 | `2f76730411299bbf909cb0778b3cda8eba593eefddfee7293962fa3ba9cef3a5` |
| Nodes | 65,536, or 4 MiB of node storage |
| Useful loads per treatment | 1,048,576 |
| Processes | One |
| Order | One chain, then eight chains |

Observed output:

```text
lanes=1 steady_ns=17284750 ns_per_load=16.484022141 sink=22274
lanes=8 steady_ns=1052916 ns_per_load=1.004138947 sink=34041
```

The CPU model string was unavailable in the sandbox. The Linux retained runs
provide the process-level comparison, complete host evidence, and generated
code.
