# Local smoke check: 2026-07-29

Host boundary: Apple arm64, Darwin 25.5.0, Rust 1.93.1, Cargo 1.93.1.

Command:

```sh
cargo run -p cpu-frontend-bottlenecks --example cost_model
```

Observed output:

```text
frontend estimate: 204.0 cycles
phase lower bound: 204.0 cycles
outlining net: 300.0 cycles; beneficial: true
```

This check validates the Rust model example. The focused benchmark requires
Linux `taskset`, GNU ELF tools, and `perf`; it runs on the retained `xxl` and
`alg` source archives instead of this host.
