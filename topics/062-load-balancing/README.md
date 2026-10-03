# Load balancing beyond round robin

Equal request shares can overload slow servers despite spare fleet capacity.
Freshness, eligible candidates, capacity, and the unit of work define a policy's
contract. This crate isolates those decisions with finite deterministic models.

```bash
cargo test -p topic062-load-balancing
cargo run --release -p topic062-load-balancing --example contracts
```

## Fixed controls

Four image-service backends start with unfinished counts `[0, 1, 1, 1]`.
There are 16 arrivals and no completions during selection.

| Selection | Final counts | Observation contract |
|---|---|---|
| Full scan | `[16, 1, 1, 1]` | Every pick sees the same unique stale minimum |
| Full scan with reservation | `[5, 5, 5, 4]` | Each pick sees this chooser's previous reservations |
| Two choices | `[7, 4, 4, 4]` | Every ordered pair, with replacement, once; stale snapshot |

The final row enumerates 16 possible pairs. It is not a random burst or an
expected maximum-queue guarantee. With two hosts and one idle, one of four
ordered pairs samples the busy host twice. A full scan can avoid that miss when
its observations are current. This model's full-scan ties use the first index;
Envoy 1.39.0 uses randomized full-scan ties. The unique-minimum counterexample
does not rely on that difference.

A second control assigns 40 equal-work requests to capacities `[4, 4, 1, 1]`
in requests per model time unit. Equal shares `[10, 10, 10, 10]` drain in ten
units. Capacity shares `[16, 16, 4, 4]` drain in four. These are exact model
calculations, not measured service throughput. With three requests ahead at a
four-request server, `(3 + 1) / 4` equals `(0 + 1) / 1` at an idle slow server.
Request count alone therefore need not rank completion time correctly.

## Limits

The crate models serialized admission, masks, hard count caps, invalid candidate
positions, empty sets, and integer overflow boundaries. It does not implement a
proxy, random sampling, concurrent reservations, completion tokens, cancellation,
heterogeneous request work, feedback control, or health-check propagation.
A timeout is not evidence that backend work ended. Production counters need a
defined release boundary and exactly-once release accounting.

Round robin fits equal costs. Capacity weights fit known stable differences.
Request-aware selection needs informative counts. Two choices trades global
search for dispersed candidate sets. Consistent hashing preserves affinity but
cannot divide a hot key. Admission limits and retry budgets remain separate.

See [round notes](rounds/01.md), [sources](references.md), and
[validation evidence](measurements/README.md).
