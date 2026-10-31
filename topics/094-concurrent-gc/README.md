# Concurrent marking and mutator costs

This fixed-object graph model compares stop-the-world tracing, unconditional
insertion marking, and snapshot-at-the-beginning (SATB) deletion marking.
Each object has one reference slot. Roots remain fixed. Scans and stores are atomic
model steps. SATB stores publish only references from the initial live set.

```bash
cargo test -p topic094-concurrent-gc
cargo build --release -p topic094-concurrent-gc --example probe
python3 topics/094-concurrent-gc/oracle.py target/release/examples/probe
python3 topics/094-concurrent-gc/measure.py target/release/examples/probe samples.json
```

The oracle uses Floyd-Warshall transitive closure. It checks 64 three-object graphs,
two stores, and 16 scan schedules. Every correct policy preserves final reachable
objects. SATB also preserves initial reachable objects. STW retains exactly the
final reachable set. `Mode::None` is a broken control tested with a hidden-live-object
counterexample; it is excluded from performance comparisons.

The benchmark runs 64 cycles of a 16,384-object chain rooted at object zero.
Every slot is rewritten once, in increasing ID order. A scan step follows stores
0, 16, 32, and so on; completion drains the queue. STW defers scanning until all
stores finish. Workloads preserve each link, clear each link, or replace each link
with a reference to object zero. Thus keep retains all objects; delete/replace
retain one for STW/insertion and all for SATB. This difference follows their
contracts. Store owners may refer to modeled slots that have become unreachable;
this exercises conservative barrier work without modeling application stack roots.

Eight fresh-process blocks use all six policy orders followed by a forward/reverse
pair. Each workload/policy has one excluded warmup. Each measured process includes
graph creation, validation, allocation, marking, stores, and destruction. Input and
policy dispatch are identical across alternatives. Rust release defaults apply.
Linux runs pin the lowest CPU in the process's allowed set and record it in the
samples file; the committed `evidence/*.json` predate that field and were pinned
to CPU 0 (see results.md). Frequency, thermals, host load and SMT are uncontrolled.

Report medians and minimum/maximum durations. Declare A faster than B only if
`t_A < 0.95 * t_B` in each of the eight paired blocks. Declare a tie if
`|t_A - t_B| <= 0.05 * max(t_A, t_B)` in every block; otherwise report unresolved.
These descriptive labels apply to the
simulator workloads. They provide no production collector ranking or confidence
interval. Scan counts describe modeled work; timings include the model's bookkeeping.

## Boundaries

The oracle validates the tested finite schedules under atomic steps. Production implementations
also need root handshakes, allocation coloring, buffer draining and termination,
weak-reference rules, compiler integration, memory ordering and reclamation.
Concurrent relocation additionally requires safe reference repair. Production
pause distributions, assist latency, CPU competition and memory bandwidth are
unmeasured here. See [results](results.md), [sources](sources.md), and [round](rounds/01.md).
