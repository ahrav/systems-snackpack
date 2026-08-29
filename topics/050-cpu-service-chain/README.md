# CPU service is a chain, not a percentage

A central processing unit (CPU) executes instructions for runnable threads. A
thread can miss a latency target while the machine looks mostly idle. The
thread may be blocked on a lock, runnable but waiting for an eligible logical
CPU, slowed by a simultaneous multithreading sibling, or waking a core from an
idle state. CPU utilization alone does not separate those delays.

Use one running example: a request thread needs a mutex held by a low-priority
refresh thread while a normal-priority compression thread remains runnable.
The refresh thread has only 60 microseconds of CPU work left. If compression
shares its logical CPU, that small amount of work can occupy far more wall
time and the request waits with it.

## Model the complete service chain

A logical CPU is a Linux scheduling target. Simultaneous multithreading (SMT)
exposes sibling logical CPUs that share one physical core. SMT can increase
aggregate throughput, but the siblings are not independent physical cores.

A thread's effective CPU set is the intersection of its requested affinity,
its effective control-group CPU set (cpuset), and the online CPU set. A cpuset
is a Linux control that restricts a group of tasks to named CPUs:

```text
effective_cpus = affinity intersect cpuset_effective intersect online
```

If affinity is `{0,1}`, the effective cpuset is `{1,2}`, and online CPUs are
`{0,1,2}`, the thread can run only on CPU 1. Affinity sets eligibility, not
reservation. It does not exclude other tasks, interrupts, kernel work, or work
on CPU 1's SMT sibling.

For one request, separate blocked, runnable, and executing time:

```text
response = dependency_blocking + runnable_queueing + own_execution
```

For one observed request, suppose the lock wait is 2 milliseconds. The request
then waits 0.4 milliseconds after becoming runnable and executes for 60
microseconds. Its response time is `2 + 0.4 + 0.06 = 2.46` milliseconds.
Optimizing only its 60 microseconds cannot recover the other 2.4 milliseconds.

The lock wait itself is approximately:

```text
lock_wait = owner_work_remaining + owner_runnable_queueing
            + owner_dependency_chain + handoff
```

For a separate lock acquisition in the same service, use 60 microseconds of
owner work, 2 milliseconds of owner queueing, no further dependency, and 15
microseconds of handoff. The wait is about 2.075 milliseconds. These are new
teaching inputs, not a decomposition of the observed 2-millisecond wait above.
Lowering the owner's priority can make the dependent request slower.

Linux ordinary fair scheduling uses a numeric `nice` value as a relative
weight. Nice 19 reduces a thread's fair-class share when it competes with
normal-priority work; it does not set an absolute CPU percentage. A futex,
short for fast user-space locking, is a Linux wait-and-wake primitive that lets
an uncontended lock stay in user space and the kernel park a contended waiter.
An ordinary mutex does not donate a waiter's priority to its owner.

The [`service_chain_cost_model`](examples/service_chain_cost_model.rs) example
exposes checked helpers for response time, lock blocking, configured fair
share, SMT aggregate gain and symmetric per-thread slowdown, deadline
utilization, and wake-to-service accounting. Its constants are teaching
inputs, not host measurements. The helpers are consistency models, not
scheduler simulations or latency predictions.

## Keep the controls separate

| Control | Problem it solves | What it does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Fair scheduling and nice weights | Shares CPU among ordinary runnable work | Deadlines, lock blocking, or SMT interference | A low-priority lock owner can delay high-priority work | Ordinary work needs proportional sharing |
| Thread affinity | Restricts where a thread may run | CPU reservation or sibling isolation | A narrow mask can strand idle capacity | Measured locality or reproducible placement matters |
| Valid control group v2 isolated partition | Removes ordinary load balancing from selected CPUs | Automatic interrupt, sibling, or kernel-work isolation | Partition setup, housekeeping, and explicit placement remain necessary | The service truly needs dedicated capacity |
| Separate physical cores | Avoids same-core pipeline sharing | Shared cache, memory, and package contention | Capacity is still workload-specific | Latency-sensitive hot threads interfere as siblings |
| SMT packing | Uses otherwise idle sibling resources | Independent-core capacity | Aggregate throughput may rise while each thread slows | Paired measurements show acceptable throughput and tails |
| Ordinary futex mutex | Parks a contended waiter efficiently | Priority donation | A descheduled owner stretches every waiter | General-purpose mutual exclusion is enough |
| Priority-inheritance mutex | Temporarily lends waiter priority to an owner | Deadlocks or long critical sections | Requires a compatible mutex and bounded dependency chain | Real-time-priority threads share an unavoidable lock |
| Fixed-priority real time | Runs higher-priority ready work first | Execution budgets or dependency analysis | A runaway thread can starve the machine | Work and recovery paths have defensible bounds |
| Deadline scheduling | Reserves runtime within a period and deadline after admission | Unmodeled locks, faults, interrupts, or overload beyond the admitted model | Underestimated runtime is throttled | A periodic or sporadic demand model passes admission and is defensible |
| Idle-latency constraint | Constrains governor selection against excessive exit latency | Runnable queueing, locks, frequency limits, or the physical state entered | It spends power and can affect a wider host | Measurement identifies wake latency as the limiting term |
| Performance-frequency request | Requests a higher target frequency within policy limits | Deep-idle exit, delivered frequency, or shared-core interference | Requested and delivered frequency can differ | Frequency behavior correlates with the measured bottleneck |

## Focused experiment

[`lock_holder_preemption.c`](experiment/lock_holder_preemption.c) creates the
request, refresh, and compression roles with three threads:

The experiment scales the running example's owner work to a 5-millisecond
thread CPU target so that fresh-process measurements remain stable enough to
audit on both required hosts.

- The refresh thread locks a mutex, raises only its own nice value to 19
  (lowering only its own priority), pins to one logical CPU, and targets 5
  milliseconds on
  `CLOCK_THREAD_CPUTIME_ID`, the per-thread CPU clock. Accepted runs measure
  from 4.9 through 6.0 milliseconds.
- The request thread pins to a different physical core and waits for the mutex.
- Treatment A pins the normal-priority compression loop to the refresh
  thread's logical CPU.
- Treatment B pins the same loop to a third physical core.

Each letter is a fresh process. On each host, eight four-process `ABBA` or
`BAAB` blocks compare A with B. Eight more four-process A/A blocks compare X
with Y when both labels execute the mechanically identical B condition. An
accepted host campaign has 16 complete blocks, 64 fresh processes, and 64
distinct process identifiers (PIDs). A complete block is one replication;
spin-loop iterations and processes inside it are not independent replications.

The comparison deliberately changes a composite condition: compression
placement plus fair-scheduler competition with a nice-19 lock owner. It does
not isolate an instruction-set architecture (ISA), a Linux scheduler
implementation detail, or SMT behavior. The accepted 4.9-to-6.0-millisecond
thread CPU range checks whether added wall time is consistent with descheduling
rather than extra owner work. It cannot identify the exact scheduler path. No
single-host result is generalized to an architecture or processor family.

The exact-source campaigns used commit
`97572e93a6ee98e14bece7501068d5cedd962571`. On the required AArch64 host,
the holder-wall A/B ratio was `39.092720`, with a 95% between-block interval
of `[38.567194, 39.625406]`. On the runtime-resolved `xxl` x86-64 host, it
was `38.855392`, with interval `[38.233483, 39.487418]`. All four holder and
waiter A/A intervals included one. These values describe two exact hosts,
native binaries, placements, workloads, and run windows. They do not estimate
a production population or compare Arm with x86.

See [`experiment/README.md`](experiment/README.md) for exact-source commands,
[`rounds/01.md`](rounds/01.md) for the frozen claim and acceptance contract,
and [`measurements/README.md`](measurements/README.md) for host records, raw
receipts, and evidence boundaries.

## Selection guide

1. Measure blocked, runnable, and executing time separately.
2. Inspect effective affinity and physical-core sibling topology.
3. Fix dependency ownership before tuning the blocked waiter.
4. Prefer separate physical cores before packing latency-sensitive work onto
   SMT siblings, then verify both throughput and tail latency.
5. Use affinity for eligibility. Use a valid control group v2 isolated
   partition to remove ordinary load-balanced work, then verify interrupts,
   siblings, and kernel work.
6. Use priority inheritance when real-time threads must share a mutex.
7. Use fixed-priority or deadline scheduling only with bounded work, overload
   behavior, and a recovery path.
8. Change idle or frequency policy only after attributing the delay to that
   part of the chain.

[`references.md`](references.md) maps each mechanism to a primary source and
states the kernel, toolchain, or hardware boundary.
