# Connection tracking and NAT limits

This single-threaded Rust model separates global flow capacity from a translated
port pool for each destination. A destination represents a remote address, port,
and protocol. There is one translated source address. All implementations return
the lowest free port, reject exhausted pools and full global state, and reject
invalid or duplicate releases. Releases represent explicit expiry/close events;
there is no timeout engine, packet path, mapping-policy implementation, or concurrency.

Candidates are a byte scan, a free-bit bitmap, and a BTreeSet of free ports.
Independent HashSet oracles check candidate outputs. Unit tests enumerate 186,624
six-event traces across four global limits and cover invalid coordinates,
exhaustion, duplicate release and 64-bit word boundaries.

```sh
cargo test -p connection-tracking-nat-limits --release
cargo run -p connection-tracking-nat-limits --release --example ports -- bitmap crowded steady
cd topics/075-connection-tracking-nat-limits
python3 run.py --out /tmp/topic075-unique --source-id local-replay
```

The output directory must not exist. The Python runner requires Rust and Python3;
Linux additionally uses lscpu and taskset. It records failed optional identity
commands as unavailable and aborts on a failed required validation/build/run.
It compares six fresh, order-balanced process blocks per candidate/workload.

Read [measurement boundaries](measurements.md), [results](results.md),
[primary sources](references.md), and [round notes](rounds/01.md).
The root catalog still has a 12-session historical ledger. This topic identity
follows the user's explicit 103-topic rotation; catalog reconciliation is separate.
