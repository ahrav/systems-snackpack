# Experiment contract

Correctness requires exact equality of ready capacity, retained desired state,
issued command, and queue against the independent Fraction oracle. Sixty seeded
80-tick traces cover measurement delays 0..7, actuation delays 1..7, arbitrary
integer demand 0..100,000, and 15% missing samples. Every policy sees each trace.

The workload comparison uses 20 paired seeds per scenario and 240 ticks per seed.
Measurement delay is two ticks; readiness delay is three ticks. Each tick is ten
seconds. Baseline demand is 6,000; service is 1,000 per ready replica; the target
is 600 arrivals per replica. Capacity is 1..40. Initial ready/desired capacity is
ten. Measurements produced at ticks 100..104 are unavailable.

- Step: demand rises to 12,000 at tick 20 and remains there.
- Burst: demand is 12,000 at ticks 20..27, then returns to 6,000.
- Noisy: independent integer demand uniformly sampled from 4,200..7,800 each tick.
- Saturation: demand is 60,000 at ticks 20..59, then returns to 6,000.

Step, burst, and saturation add integer noise uniformly sampled from -300..300
at ticks 20..79. Thus their final 160 ticks have constant demand. Seeds 0..19
are shared across policies. Variation describes these input traces. It is not a
confidence interval over real workloads or a machine-speed measurement.

Report peak queue, sum of post-service queue over ticks, final queue, total ready
replica-ticks, command-change count, and final 40-tick ready-count span. Lower queue
and capacity cost can conflict. Compare each objective separately; use final queue
and persistent capacity oscillation to identify recovery failures. A stable
capacity count alone does not establish acceptable queue-drain behavior.

The model assumes homogeneous replicas, linear service capacity, instantaneous
service accounting within each tick, ordered absolute commands, fixed symmetric
readiness delays, and perfect arrival counts except declared missing samples.
Physical startup distributions, request latency, throughput measurements, metric
bias, cancellations, retries, multiple controllers, and provider semantics require
separate experiments. No production tuning recommendation follows from these
synthetic workloads alone.

# Observed results

Tested source: `936c93f1f6ee13a7dd705596f4fadf315b00c5f6`.

Local macOS arm64, Linux AArch64, and Linux x86_64 each pass 72,000 complete
state comparisons (288,000 field comparisons), three unit tests, and one doctest.
All three have identical state-output digests. The workspace pins Rust 1.93.1;
builds use the release profile. Each host JSON retains the platform string,
machine architecture, and Python version. The Linux run logs also retain the
archive SHA-256, `uname -a`, `lscpu`, and the `rustc` version. The local log
retains the test and release-build output; the local CPU model and `rustc`
version were not captured. These are deterministic simulation outcomes; host
runtime speed is outside the experiment.

| Workload | Policy | Queue area median [min, max] | Replica-ticks median | Command changes median | Final queue median |
|---|---|---:|---:|---:|---:|
| step | fast | 3,345,047.0 [3,233,871, 3,620,805] | 4,718.0 | 109 | 25000 |
| step | slow | 59,195.0 [53,939, 65,833] | 4,525.0 | 10 | 0 |
| step | feedforward | 31,493.0 [28,619, 34,867] | 4,581.0 | 31.5 | 0 |
| burst | fast | 1,672,554.0 [1,642,251, 1,691,639] | 3,976.5 | 134 | 0 |
| burst | slow | 55,864.5 [51,036, 61,645] | 2,484.0 | 17 | 0 |
| burst | feedforward | 31,493.0 [28,619, 34,867] | 2,511.0 | 32.5 | 0 |
| noisy | fast | 1,721,690.0 [1,605,368, 2,030,437] | 3,929.0 | 156 | 6243 |
| noisy | slow | 0.0 [0, 0] | 2,385.0 | 43.5 | 0 |
| noisy | feedforward | 0.0 [0, 0] | 2,502.0 | 197 | 0 |
| saturation | fast | 58,370,364.0 [58,150,887, 58,552,887] | 4,803.0 | 112 | 0 |
| saturation | slow | 90,272,439.0 [90,028,987, 90,634,038] | 3,668.0 | 19 | 12088 |
| saturation | feedforward | 99,423,607.5 [98,959,243, 100,030,770] | 3,611.0 | 13 | 68910.5 |

Queue area sums post-service queued requests across ten-second intervals. Multiply
by ten for the sampled request-seconds proxy. Replica-ticks count ready capacity;
billing and provisioning costs are outside this model. Full ranges for every
metric and seed-zero traces are retained in the host JSON.

Step and burst: feed-forward has lower queue area than slow in all 20 paired
seeds. Slow uses fewer replica-ticks and command changes in all 20 seeds. Both
reach constant ready capacity and empty queues during the final 40 ticks. Each
favors a different objective; choose using a queue/cost budget.

Noisy demand: slow and feed-forward tie at zero queue in all 20 seeds. Slow
uses fewer replica-ticks and command changes in all 20 seeds. Slow is preferred
for these declared objectives on this workload.

Saturation: fast has lower queue area than both other policies in all 20 seeds,
while its final ready capacity continues spanning 1..40. That queue-area result
does not establish stable recovery. Slow has lower queue area than feed-forward
in all 20 seeds; feed-forward uses fewer replica-ticks. Both remove capacity
while old work remains queued because decisions depend on arrivals and ready
capacity. Slow ends with 10,606..14,190 queued requests; feed-forward ends with
66,448..72,905. Neither clears the surge backlog within the experiment. A
backlog-aware controller and explicit drain-time objective are the next experiment.
All policies exceed available service during the surge.

Fast keeps a final ready span of 39 on every workload and every seed: the
`final_ready_span` minimum and maximum are both 39 in each host JSON summary.
This persistent oscillation occurs after noisy step/burst/saturation transients
end. Lowering gain removes that cycle in the tested constant-load tails. The
lower gain alone leaves the saturation-recovery queue problem unresolved.

These traces support workload-specific comparisons. Production stability,
untested delay distributions, and universal optimal gains require further
evidence. The model omits dependency saturation and service-time drift.

Raw JSON is retained losslessly as `measurements/{local,arm,x86}.json.gz`.
Read it with `gzip -dc measurements/arm.json.gz`. Identity files record archive,
raw-data, and compressed-data SHA-256 values. The exact tested source archive
contains workspace manifests, toolchain pin, and this topic's files. The Linux
host scripts verify its hash before extracting, compiling, and running it, and
their logs retain the hash line. The local identity file records the same archive
hash; the local log starts at the test build.

Commits after the tested source correct documentation, reorder the diagram
label, and add one unit test to `src/lib.rs`. That test covers both gain
policies with a fractional deficit, ceiling rounding, and the lower clamp. The
tested source ran three unit tests on each host; the head runs four, checked on
Linux x86_64 with Rust 1.93.1. `simulate`, `src/main.rs`, and
`experiment/check.py` are byte-identical to the tested commit, and the head
release binary reproduces the recorded state digest on Linux x86_64.
