# Frozen comparison

Outcome: wall time from releasing ready workers until all joins complete, divided
by completed requests. Thread creation and affinity setup are excluded. Barrier
release, lock acquisition/release, computation, and worker teardown are included.
Sequential checksum validation follows timing. No updates occur in timed runs.
The separate correctness test exercises concurrent whole-version replacement.

Treatments: mutex held through compute, read guard held through compute, and read
guard released after copying the 16-byte version. Snapshot semantics are legal
for this read-only workload and for the stated per-request version contract.
Do not infer equal freshness for a different application.

Six cells per host: 1/4/8 workers; 0/256 dependent arithmetic rounds per request.
Short cells perform 250,000 requests per worker; long cells perform 12,000.
One warmup per candidate/cell; six fixed measured repetitions. Each repetition
uses a different permutation of all three candidates, in lexicographic order.
Cell order reverses every repetition. No randomization or optional stopping.
Every failed attempt is retained; a failure invalidates that cell's verdict.

A process receives a treatment. One complete repetition supplies paired candidate
contrasts. Requests are subsamples. These are shared-host descriptive observations,
not independent population samples. One build per host; no build or host-population
replication, power target, significance test, confidence bound, or familywise claim.
The fixed budget is six comparisons; variability may leave cells unresolved.

Two identical rwlock invocations test A/A command, parsing, checksum and artifact
identity. Their timing is diagnostic only. This is not null calibration and does
not establish a noise floor. Fresh processes reset locks, threads and payloads;
CPU/cache/thermal state can persist. Warmups and balanced order reduce some order
sensitivity but do not remove shared-host interference or carryover.

Record median and min/max ns per completed operation. For every pair within a
cell, candidate A is a descriptive winner only if all six paired B/A time ratios
exceed 1.05. A practical tie requires every ratio in [1/1.05, 1.05]. All other
comparisons are unresolved. Declare an overall cell winner only if it beats both
alternatives. The rule is fixed before data and is not a confidence interval.

Use eight distinct visible cores in one socket/NUMA node, chosen from the allowed
CPU set. Pin each worker to its own CPU and read back its singleton affinity before
timing. Record topology; virtual CPU topology need not prove physical isolation.
Rust 1.93.1, opt-level=3, target-cpu=native, codegen-units=1, LTO off, panic unwind.
Prebuilt standard library remains its installed target build. No governor changes,
CPU reservation, NUMA memory binding, PMU, off-CPU profiling, writer-latency or
open-loop arrival measurement. Source inspection motivates mechanism hypotheses;
these timings cannot isolate coherence, scheduling, and code-generation effects.
