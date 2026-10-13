# Consistent-hashing movement

Compare modulo, HRW, and fixed rings with 1 or 64 positions per stable node ID.
The contract distinguishes changed owners, unrelated survivor changes, and cumulative
remove-then-add transfers. Placement is not a migration protocol.

```sh
cargo test -p consistent-hashing-movement
cargo build --release -p consistent-hashing-movement --example placement
./target/release/examples/placement movement
python3 topics/076-consistent-hashing-movement/run.py target/release/examples/placement /tmp/topic076-results
```

`src/lib.rs` carries the independent oracle and edge contracts. `run.py` captures
host/toolchain identity and six balanced process blocks per workload.
Read `measurements.md` before interpreting `results.md`.
