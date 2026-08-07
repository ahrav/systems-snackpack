# Queueing service design

Equal mean service demand does not imply equal waiting time. Long jobs can hold
an FCFS worker while short jobs accumulate behind them. With a bounded
queue, that delay becomes rejection and lost goodput once the waiting slots
fill.

This topic makes that mechanism observable in one deliberately small system.
It is an executable note, not a general queue simulator or a production sizing
rule.

## Focused model

| Element | Contract |
| --- | --- |
| Arrival process | Deterministic open-loop intended arrivals; completions never schedule later arrivals |
| Server | One non-preemptive FCFS worker |
| Admission | Non-blocking admission to four waiting slots; a full queue rejects the request |
| In-system bound | At most four waiting jobs plus one job in service |
| Fixed treatment `A` | Every offered request receives `1x` calibrated work |
| Variable treatment `B` | Every ten-request group contains nine `0.25x` jobs and one `7.75x` job |
| Horizon | 8,000 intended arrivals in every fresh process |
| Offered load | Nominal `rho = 0.9`, using a per-host calibration near 200 us for `1x` work |

For one worker, the runner sets
`interval_ns = calibrated_mean_service_ns / 0.9` (with its recorded integer
rounding), so `rho = E[S] / interval` is nominally `0.9` for both offered
service shapes.

The variable treatment preserves offered mean work exactly:

```text
E[S] / base = (9 * 0.25 + 1 * 7.75) / 10 = 1
E[S^2] / base^2 = (9 * 0.25^2 + 1 * 7.75^2) / 10 = 6.0625
offered Cs^2 = E[S^2] / E[S]^2 - 1 = 5.0625
```

The long-job position is deterministic from the recorded workload seed and
ten-request group. These are offered-service properties. Bounded admission can
make the service distribution of completed requests different, so completed
service means must not be used to claim that offered work was unmatched.

## Measurement boundary

Each raw request row records:

- intended arrival;
- actual generator admission attempt;
- service start for admitted work;
- completion, or rejection at the admission attempt.

Queue wait is `service start - actual attempt`, conditional on completion.
Generator lateness is `actual attempt - intended arrival`. Rejection is
reported against all offered requests. Goodput is completed useful requests
divided by the later of the nominal arrival horizon and final completion time.
It remains separate from offered rate, admitted rate, and raw worker
throughput.

This separation matters. An open generator can still fall behind its intended
schedule, and a finite queue can preferentially reject one part of a service
distribution. The raw timestamps make both effects inspectable.

## Run locally

From the repository root:

```bash
cargo test -p queueing-service-design
cargo build --release -p queueing-service-design --bin queue-probe

target/release/queue-probe --calibrate 200000

python3 topics/027-queueing-service-design/experiment/run_processes.py \
  target/release/queue-probe \
  /tmp/topic27-local \
  0,1

python3 topics/027-queueing-service-design/experiment/analyze.py \
  /tmp/topic27-local > /tmp/topic27-local/analysis.json

python3 topics/027-queueing-service-design/experiment/validate_receipts.py \
  /tmp/topic27-local
```

The runner calibrates one fixed-service job near 200 us, derives the
deterministic interval for nominal `rho = 0.9`, and launches every period in a
fresh process. A direct process invocation uses:

```text
queue-probe \
  --mode fixed|variable --label A|B --phase main|aa \
  --block N --period N --seed N \
  --requests 8000 --queue-cap 4 \
  --base-iters N --interval-ns N --raw PATH
```

The complete assignment, estimator, and failure policy are predeclared in
[round 1](rounds/01.md).

## Exact-candidate result

Commit `bf93921` completed the full schedule on the literal Arm host and on
`xxl`, resolved at run time to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`. At matched offered mean loop
work, the variable service shape increased block-level mean queue wait by about
`0.508 ms` on Arm and `0.500 ms` on `xxl`, increased rejection by `21.6664`
and `22.6492` percentage points, and reduced goodput to `0.782825` and
`0.773017` of the fixed treatment. These are two source-, host-, workload-,
and run-window-specific observations, not architecture effects. The full
[comparison and intervals](measurements/bf93921-comparison.md) keep those
boundaries explicit.

## Exact-candidate rerun gate

A local run is a harness check. Host results enter only after the exact
candidate is committed, archived, hashed, and rerun without source changes on:

- runtime alias `xxl`, with its backing hostname resolved and recorded at run
  time; and
- literal Arm endpoint
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`.

Run the wrapper from a clean checkout of that exact commit:

```bash
topics/027-queueing-service-design/experiment/run_host.sh \
  /absolute/path/to/repository \
  /absolute/path/to/output \
  HOST_LABEL \
  FULL_SOURCE_COMMIT
```

The wrapper verifies `HEAD`, refuses a dirty worktree, creates and hashes a
source archive, records tracked-source and binary hashes, then runs and
validates the fixed schedule. Do not fill a failed period after inspecting
results. A corrected or repeated experiment gets a new candidate or run
identity and the whole fixed schedule.

## Claim boundaries

- **Source:** a result belongs to the recorded commit, source archive, tree
  manifest, compiler invocation, final binary digest, schedule, and run window.
  A working-tree run is not exact-candidate evidence.
- **Model:** this is one deterministic open-arrival, single-worker, bounded
  FCFS system without retries, deadlines, cancellation, multiple servers, or
  adaptive admission. Little's Law concerns matched long-run means. Kingman's
  heavy-traffic result explains why variability can amplify waiting, but it is
  not a numeric prediction for this finite, shedding queue.
- **ISA:** final-image inspection can show that the intended timing loop and
  call path survived optimization. Cross-host elapsed differences do not by
  themselves establish an ISA, vendor, or processor-family effect.

The retained-record contract is in [measurements](measurements/README.md), and
the mechanism-to-source map is in [references](references.md).
