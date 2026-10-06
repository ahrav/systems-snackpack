# Frozen experiment

- Eight paired process blocks per workload. Four cyclic orders followed by their
  reverses balance candidate positions and pairwise precedence. 192 processes/host.
- Each process warms up a separate lock and workers for 20 operations/worker.
- Before timing, every measured worker passes a readiness barrier. Time covers
  release through joining workers. Lock instrumentation, exclusion checks, atomic
  payload operations, and checksum arithmetic are included. Thread creation,
  allocation of shared state, warmup, post-run serial oracle, and output are excluded.
- Process CPU time uses CLOCK_PROCESS_CPUTIME_ID. It is aggregate CPU usage over
  approximately the wall interval, not latency or energy.
- Cases: one worker/100000 operations; four workers/10000 each with one arithmetic
  step; four/2000 with256steps; eight/2000 on one CPU; four/50 with a requested50us
  sleep while holding the lock; four/one operation. The other cases use four CPUs.
- CPUs are the first allowed logical CPU IDs, not asserted independent physical
  cores. No governor, host workload, NUMA, or cache-flush intervention is made.
- No parallel benchmark processes on a host. Optimization3, target-cpu=native,
  Rust2024, default panic unwind and LTO policy. Exact compiler, kernel, affinity,
  feature cfg, binary hashes and disassembly are retained externally.
- Each process checks exclusion and completed work against a separate sequential
  traversal. Reject any incorrect candidate before selecting from timings.
- Criterion: smallest median wall ns/op; at least2% below each other median and
  each paired 95% bootstrap median-ratio upper bound below1. Resample eight process
  blocks10000times with seed69. Otherwise report unresolved. This is descriptive
  evidence from a small shared-host sample, not a population guarantee or a
  multiple-comparison-corrected confidence claim. Report IQR and CPU cost too.
- Initial scratch timing included arrival at the first barrier. That campaign is
  retained but does not match the final boundary. A second barrier fixes readiness
  before final exact-source timing. No selection pools initial and final runs.
- Wait counters count syscall attempts; EAGAIN counts rejected sleeps. Successful
  wake returns count woken waiters, not progress or scheduling events. No trace
  proves individual lock-holder preemption. The one-CPU short case can serialize
  without contention. Burst uses warm process state, not a cold-cache experiment.
- String policy selection, atomic sentinel and payload, syscall counters, and the
  simplified repeated swap slow path are part of the treatment. These numbers do
  not rank std::Mutex, parking_lot, or whole architectures.

Replay the frozen path-limited input with `bash scripts/remote.sh` from its topic
directory. INPUTS.sha256 is checked before compilation and after measurement.
