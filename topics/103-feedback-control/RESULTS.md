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
