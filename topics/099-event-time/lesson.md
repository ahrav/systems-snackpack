# What this lesson is trying to teach

Event-time aggregation needs explicit rules for emission, correction and state deletion.
A watermark supplies progress information. The application decides what that progress permits.
Topic 099 uses sales in ten-second windows across two input partitions.

## If you remember only these things

- Event time comes from the event. Processing time is when the operator handles it.
- A watermark expresses expected progress; its accuracy depends on source assumptions.
- Combine active inputs using their minimum progress. Quiet inputs can hold every window open.
- First emission, retained corrections and cleanup require separate rules.
- Full corrected totals require sink replacement; adding successive totals double-counts sales.

## Define the boundary

A tumbling window groups records into fixed, nonoverlapping intervals: [0,10), [10,20), etc.
Timestamp 10 belongs to the second window. Our exclusive frontier F means future event
timestamps are expected to satisfy t >= F. Window [s,e) first emits at F >= e.
Flink's inclusive watermark W covers timestamps through W. For integer timestamps,
F = W + 1 translates our convention. Verify the deployed API's equality rules.

Allowed lateness L retains a window for corrections after emission. Our model accepts
records while F < e+L, removes state at F >= e+L, and counts later records in its late
output. Production reconciliation must retain the rejected records themselves.

## Running example

Sales (timestamp=2, amount=5) and (7,7) give total 12 for [0,10).
A reports frontier 14 and B reports 10. Their minimum is 10, so the operator emits 12.
A delayed sale (8,3) arrives. With L=5, the operator emits replacement total 15.
Both inputs then reach 15, allowing cleanup. A subsequent sale (9,4) goes to late output.

Render `watermarks.dot` with `dot -Tpng watermarks.dot -o watermarks.png`. The retained standalone lesson includes the inspected image.

The PNG was rendered with Graphviz and visually inspected. The repository retains the
DOT source; this standalone copy includes the rendered image.

## Generation, idleness and resumption

One policy sets each partition's frontier to maximum observed event timestamp minus
an assumed disorder bound. Maximum 20 and bound 6 yield frontier 14. This is an estimate
unless the source supplies a matching ordering guarantee. Device clock errors, replay,
outages and timestamp outliers can break the assumption. Validate timestamp plausibility
before allowing an outlier to advance progress.

Flink uses the minimum of active input watermarks. Idle detection excludes quiet inputs.
If B stays at 4 while A reaches 100, B holds progress at 4. Excluding B permits progress
toward 100 and may delete old state. If B resumes at timestamp 7, reconciliation may be
required. An idle timeout changes completeness policy; it cannot prove old records will
never return. Our model holds progress when all inputs are idle and never regresses it.

Watermark alignment can pause fast sources to constrain skew and downstream buffering.
Its costs include reduced consumption and upstream backlog. Watermarks must follow the
completion of the input records they describe, including asynchronous processing.

## Alternatives and selection

| Policy | Useful when | Cost or failure mode |
|---|---|---|
| Processing-time windows | Arrival time defines the intended metric | Replay/delay changes membership |
| Event time, zero lateness | Fast cleanup with a separate reconciliation path | Delayed records miss online totals |
| Event time, retained corrections | Early totals plus later corrections | More state and sink writes |
| Complete bounded input | Final batch result is acceptable | Latency includes input completion |

A trigger decides when to emit. Early triggers may publish before the frontier reaches
the window end. Accumulating outputs contain full totals; discarding outputs contain
contributions since the prior firing. Consumers must know which contract applies.

Our sink receives 12 and 15 and must finish at 15. Use a stable key such as
(merchant, window_start) and replacement semantics. An asynchronous sink needs ordered
or versioned updates so a retry of 12 cannot overwrite 15. Delta outputs instead require
deduplication of retried deltas. Watermark progress does not establish durable recovery
or event uniqueness. Recovery must coordinate source positions, state, timers and sink
effects. Test that protocol separately under the chosen runtime.

## Runnable boundary example

Run `python3 window_demo.py`. It isolates one window after input frontiers are combined.
Expected output is `upsert 12`, `upsert 15`, `late 9 4` on separate lines.

```python
end, lateness = 10, 5
frontier = -1
total = 0
present = False
fired = False


def event(timestamp, amount):
    global total, present, fired
    assert 0 <= timestamp < end
    if frontier >= end + lateness:
        print("late", timestamp, amount)
        return
    total += amount
    present = True
    if frontier >= end:
        fired = True
        print("upsert", total)


def advance(value):
    global frontier, total, present, fired
    assert value >= frontier
    frontier = value
    if present and not fired and frontier >= end:
        fired = True
        print("upsert", total)
    if frontier >= end + lateness:
        total, present, fired = 0, False, False


event(2, 5)
event(7, 7)
advance(10)
event(8, 3)
advance(15)
event(9, 4)
```

## Generalized Rust model and independent oracle

From the repository root:

```bash
cargo +1.93.1 test -p topic099-event-time
cargo +1.93.1 build -p topic099-event-time --example replay
cargo +1.93.1 run -q -p topic099-event-time --example replay < topics/099-event-time/experiment/demo.txt
python3 topics/099-event-time/experiment/check.py target/debug/examples/replay
```

Replay commands are `E input timestamp amount`, `W input frontier`, `I input`,
`A input`, and `R lateness`. Output columns are frontier, rejected count, replacement
write count, retained aggregates and sink aggregates. Map entries use `start:total`;
`-` denotes an empty map. The demo ends with `15 1 2 - 0:15`.

The Python oracle retains accepted raw events and independently recomputes grouped sums
with SQLite. It derives initial emission from old/current frontier crossings. The Rust
model stores incremental sums and detects initial emission using sink membership.
Checks compare both maps, progress, rejection count and output count after every command.
The workload includes 720 permutations at each of four lateness values plus 300 seeded
100-command schedules. Equality, zero lateness, absent earlier panes, idle resumption,
all-idle states, stale watermarks, negative adjustments and window-boundary timestamps
appear in the schedules. This samples a finite input space; it is not a general proof.

The model has two partitions, one implicit merchant, width 10, nonnegative integer time,
unique events and ordered sink replacements. Inputs and sums must fit i64 arithmetic.
Assertions and checked arithmetic reject invalid values/overflow. Explicit idle commands
represent policy decisions; real-time idle detection is outside this model.

## Costs and evidence limits

The model stores one aggregate per live window and scans retained windows on progress
changes. A production implementation can use ordered timers. The retained sink map is
an observable output store and grows with emitted windows; count it separately from
operator window state. The checker retains event history for correctness, not efficiency.

For K continuously active keys, width D, lateness L and progress lag H, a rough estimate
is K * (1 + ceil((H + L)/D)) live aggregates. It assumes bounded timestamp spread.
Stalled progress and far-future timestamps can retain much more state. Monitor per-input
progress, idle duration, retained bytes/windows, corrections, expired records and sink lag.
Choose lateness from measured delay distributions and the cost of omitted records.

This is a deterministic correctness experiment. Throughput, production memory,
checkpoint recovery, deduplication, and real-world watermark accuracy remain unmeasured.
See results.md for exact-source host results and validation.

## Primary sources

- [Flink time semantics](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/concepts/time/): inclusive watermarks.
- [Flink windows](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/datastream/operators/windows/): lifecycle, maximum timestamp, lateness and side outputs.
- [Flink watermark generation](https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/datastream/event-time/generating_watermarks/): minimum propagation, idleness and alignment.
- [Beam triggers](https://beam.apache.org/documentation/programming-guide/#triggers): emission and accumulation contracts.

Sources checked 2026-11-05. The custom simulator is not a Flink or Beam runtime test.
