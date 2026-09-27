# Deterministic simulation and model checking

Two workers each increment a counter once. Splitting each increment into read
and write transitions creates six legal schedules. Four lose an update. Making
each increment one indivisible transition creates two safe schedules.

This is an explicit trace-tree search of a finite model. It is not a randomized
simulator, native-thread test, weak-memory model, or proof about production code.
Every unfinished worker is enabled, every step advances a worker, and no crashes,
waiting loops, retries, or external effects exist. Termination is built in.

```sh
cargo run -p topic060-deterministic-simulation --example explore
cargo test -p topic060-deterministic-simulation
```

## Contracts and controls

- The terminal oracle requires counter == completed workers == 2.
- Split mode is the negative control: 6 terminal schedules, 4 failures, 18 edges.
- Atomic mode is the safe model control: 2 terminal schedules, 0 failures, 4 edges.
- Split mode at depth 3 has no terminal schedules and six cutoffs. It is not a pass.
- A terminal state at the depth bound is checked before cutoff detection.
- Replay consumes exact worker choices and rejects unknown or finished workers.
  An incomplete prefix has no terminal verdict. The first counterexample is
  `[0, 1, 0, 1]`, which replays to value 1 with two completed workers.
- No state merging occurs. A future visited-state key would need the counter,
  worker positions, and saved read values, not just the shared counter.

For n workers with k always-enabled ordered steps each, complete interleavings
number (n*k)!/(k!)^n. Here 4!/(2!)^2 = 6. Changing model atomicity changes the
question: combining a real split update into one transition would hide the bug.

Replay needs exact source, model, initial state, configuration, and choices.
A seed alone is insufficient when event ordering or random consumption changes.
Random sampling, exhausted finite search, and resource-limited search carry
separate evidence claims. None establishes liveness under an arbitrary scheduler.

## Evidence

See [measurements](measurements/README.md) for host identities, final-source
receipts, and limits. Timing is not useful for this correctness question. Assembly
inspection confirms the compiled search path, not model fidelity or CPU atomics.

## Primary sources

See the [source ledger](references.md) for versions and claim boundaries.

- [FoundationDB 7.4.8 simulation and testing](https://apple.github.io/foundationdb/testing.html):
  deterministic cluster simulation complements live performance and hardware tests.
- [Loom 0.7.2](https://docs.rs/loom/0.7.2/loom/): instrumented concurrency testing,
  preemption bounds, and limits of relaxed-memory modeling.
- [Lamport, Specifying Systems (2002), chapters 7, 8, 14](https://lamport.azurewebsites.net/tla/book-02-08-08.pdf):
  atomicity, fairness, finite model checking, and specification boundaries.

These sources motivate the distinctions. Counts and replay outcomes come from
this repository's model and tests, not from those tools.
