# Backpressure and overload control

A synchronized miss wave can turn one missing value into many identical origin
calls. If every caller retries independently, retries amplify the overload that
caused the failures. A concurrency semaphore limits how many calls run at once,
but it does not remove the duplicate work waiting behind the semaphore.

This topic isolates a bounded alternative for one active key: coalesce callers
into one flight, give that flight one retry budget, bound physical origin
concurrency, and shed logical callers above a separate waiter cap. The artifact
is a synthetic concurrency experiment, not a DNS resolver or a production
control policy.

## Mental model

Think of a *flight* as one receipt shared by callers asking for the same key.
The first admitted caller is the leader. It performs physical attempts. Other
admitted callers are followers: they wait for the leader's terminal result
instead of starting their own work.

```text
64 callers for key K
        |
        +-- admission cap W ----------------------------------+
        |                                                     |
        +-- naive: 64 independent flights                     |
        |      each owns 2 retry tokens                        |
        |      64 * (transient, transient, success)            |
        |                                                     |
        +-- controlled: 1 key-scoped flight                   |
               1 aggregate budget of 2 retry tokens           |
               (transient, transient, success)                |
               one terminal result wakes all 64 callers ------+

All physical attempts also acquire from one origin permit pool of size C=4.
```

The controls bound different populations. The waiter cap bounds admitted
logical callers. Singleflight bounds duplicate work for one key. The retry
budget bounds attempts by one flight. The origin permit pool bounds physical
attempts executing at the same time. None substitutes for the others.

## Count and cost model

Let:

- `N` be logical callers;
- `W` be the admitted-caller cap, including the controlled leader;
- `C` be the physical origin-concurrency cap;
- `M` be maximum attempts per flight;
- `Q` be retry tokens available after a flight's first attempt; and
- `s` be the first synthetic attempt that succeeds.

For this artifact, `s = 3` and every flight sees `transient, transient,
success`. The exact admitted and shed counts are:

```text
A = min(N, W)
shed = N - A
k = min(M, 1 + Q, s)       attempts made by each flight
```

The treatment changes only the number of flights:

```text
F_naive      = A
F_controlled = 1 when A > 0

origin_attempts = F * k
retry_attempts  = F * (k - 1)
completed       = A when k = s, otherwise 0
retry_exhausted = A when k < s, otherwise 0
peak_origin_active <= C
peak_admitted      <= W
```

If one calibrated attempt has nominal work cost `t`, the modeled physical work
is `F * k * t`. That is a work-accounting identity, not an elapsed-time
prediction: permit waits, scheduling, synchronization, and host interference
remain in the measured burst time.

With the default `N=W=64`, `C=4`, `M=3`, and `Q=2`:

| Count per process | Naive | Controlled |
| --- | ---: | ---: |
| Admitted / shed | 64 / 0 | 64 / 0 |
| Independent flights | 64 | 1 |
| Leaders / followers | 0 / 0 | 1 / 63 |
| Physical attempts | 192 | 3 |
| Retry attempts | 128 | 2 |
| Transient / successful attempts | 128 / 64 | 2 / 1 |
| Logical completions | 64 | 64 |

Controlled mode therefore performs one sixty-fourth as many physical attempts,
a `64:1` reduction factor, in this fixed one-key wave. That count reduction is
deterministic. Any elapsed-time ratio is a host- and run-window-specific
measurement.

## Technique comparison

| Technique | What it bounds | What remains unbounded or duplicated |
| --- | --- | --- |
| Independent retries | Per-caller attempts, if each caller has a cap | Budgets multiply by admitted callers |
| Origin concurrency cap | Simultaneously executing physical attempts | Duplicate attempts can accumulate behind the cap |
| Key-scoped singleflight | Concurrent duplicate work for one key | Followers without a waiter cap; retries without a budget |
| Aggregate retry budget | Attempts made by one flight | Number of flights unless work is coalesced |
| Waiter cap and shedding | Logical callers retained for one key | Physical duplication among retained callers |
| Composed controlled path | One-key flights, retries, waiters, and active origin work | Multiple-key population, global fairness, and recovery |

Backpressure must terminate in an explicit policy. Here, origin work waits for
a permit, but callers above `W` are shed immediately. Replacing shedding with
an unbounded queue would move overload into latency, memory, and thread count.

## Why deterministic backoff is absent

The physical-attempt loop contains no sleep because a fixed backoff would add
wall-clock delay while leaving synchronized naive callers on the same fixed
schedule; it tends to preserve their phase and renewed contention. Production
retry guidance therefore uses randomized jitter. Adding
jitter here would introduce a second randomized treatment and make burst time
depend on a backoff distribution, obscuring the count effect of coalescing and
shared budgeting. Backoff, jitter, deadlines, and recovery timing need their
own experiment with a declared schedule and estimand.

Omitting backoff does **not** recommend immediate retries in production. It
keeps this experiment focused on duplicate suppression and hard count bounds.

## One-key and global boundary

The key digest is an identity token; no lookup occurs. Singleflight state, the
waiter cap, and the retry budget apply to one key. The origin permit pool is
process-wide, but this experiment activates only one key, so it cannot measure
cross-key fairness or head-of-line effects.

There is no global active-key cap or global admitted-waiter cap. If a production
implementation independently admitted `K` hot keys, key-scoped controls alone
could retain up to `K * W` callers and create up to `K` flights. A shared
origin pool could still keep physical concurrency at `C`, while queued work and
memory grew with `K`. That is an extrapolated risk boundary, not a result of
this one-key run.

## Failure modes and omissions

- A concurrency cap alone can preserve a large stale queue after callers no
  longer care about the result.
- Per-caller retry limits still multiply physical work by caller count.
- Singleflight without a waiter cap converts origin overload into follower
  memory or thread pressure.
- A waiter cap without key coalescing sheds some callers while retained callers
  continue duplicate retries.
- A shared flight needs production rules for leader cancellation, panic,
  timeout, cleanup, and takeover. This artifact supplies none of them.
- Deterministic backoff can preserve synchronization; jittered backoff is
  omitted rather than approximated incorrectly.
- Per-key controls do not supply global active-key bounds, tenant fairness, or
  fleet-wide retry budgets.

The artifact also omits real DNS messages, sockets, network loss, resolver
selection, positive and negative TTL caching, transport fallback, response
validation, deadlines, cancellation, adaptive throttling, backoff and jitter,
outage recovery, cache repopulation, multiple keys, and key lifecycle. The
synthetic result schedule is fixed rather than sampled from a failure process.

## Run locally

From the repository root:

```bash
cargo test --locked --package backpressure-overload
cargo build --locked --release --package backpressure-overload --bin overload-probe

target/release/overload-probe --self-check

python3 topics/028-backpressure-overload/experiment/run_processes.py \
  target/release/overload-probe \
  /tmp/topic28-local

python3 topics/028-backpressure-overload/experiment/analyze.py \
  /tmp/topic28-local > /tmp/topic28-local/analysis.json

python3 topics/028-backpressure-overload/experiment/validate_receipts.py \
  /tmp/topic28-local
```

The output directory must not already exist. On success the self-check prints
exactly `self-check: PASS`. The full runner creates 48 scheduled fresh-process
periods plus two semantic-control processes after calibration. The analysis
schedule contains 32 main periods in eight four-period blocks and 16 controlled
A/A periods in four blocks. Each main block contains two naive and two
controlled periods. Every default period has 64 logical rows; naive periods
have 192 physical-attempt rows and controlled periods have 3.

The two semantic controls exercise the bounds rather than enter the timing
analysis:

- `N=128, W=64, Q=2`: 64 completed, 64 shed, one flight, and three attempts;
- `N=64, W=64, Q=1`: 64 retry-exhausted, none completed or shed, one flight,
  and two transient attempts.

The validator recomputes all scheduled and semantic-control counts from raw
receipts.

For retained Linux evidence, run the wrapper from a clean checkout of the full
candidate commit:

```bash
topics/028-backpressure-overload/experiment/run_host.sh \
  /absolute/path/to/repository \
  /absolute/path/to/output \
  HOST_LABEL \
  FULL_40_HEX_SOURCE_COMMIT
```

The wrapper refuses an existing or in-repository output path, a dirty worktree,
and a `HEAD` that differs from the requested commit. A local run remains a
harness check until the exact candidate passes independently on both required
hosts.

The primary timing metric is `burst_ns`, from synchronized release through the
end-barrier rendezvous after every caller has settled. It includes barrier
release overhead and is not exactly the maximum caller settlement timestamp.
Thread creation is recorded separately as `setup_ns`; joins and CSV
serialization occur after the burst endpoint. The primary analysis is the
controlled/naive burst-time ratio over eight complete block contrasts. See
[round 1](rounds/01.md) for the estimator and failure policy.

## Measured, derived, and inferred

- **Measured:** per-caller admission and settle timestamps, per-attempt queue,
  start, and end timestamps, process burst and setup time, active origin count
  at attempt start, and host/toolchain identity in an exact-source run.
- **Exactly derived and validated:** logical status counts, flight and retry
  counts, checksums, cap conformance, schedule identity, and block contrasts.
- **Inferred only:** how a real resolver, network dependency, multiple-key
  service, or fleet would behave. The count model explains a mechanism; it does
  not establish a production capacity or latency result.

The exact-source promotion contract is in [measurements](measurements/README.md),
and the mechanism-to-source map is in [references](references.md).
