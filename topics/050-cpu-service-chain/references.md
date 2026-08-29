# Topic 50 primary sources

Each source below supports one bounded claim. Upstream documentation and source
do not establish the behavior of a deployed kernel, virtual machine, Rust
toolchain, or processor without matching that system's recorded identity.

## Host, kernel, and toolchain boundary

- [`kernel.org`](https://www.kernel.org/) identifies upstream release state.
  `docs.kernel.org` and `torvalds/linux` links below follow upstream; distribution
  patches, backports, configuration, boot arguments, and loaded schedulers can
  change a host's behavior without changing its `uname` architecture string.
- Results in this topic apply only to the recorded run windows on the Arm target
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` after it reports `aarch64`,
  and the runtime-resolved backing host for alias `xxl` after it reports
  `x86_64`. A virtual machine can expose topology and power
  controls chosen by its provider, so host receipts must record `uname`, CPU
  model, online topology, kernel configuration evidence, compiler identity,
  and available interfaces.
- [`rust-lang/rust`'s current futex mutex
  source](https://github.com/rust-lang/rust/blob/main/library/std/src/sys/sync/mutex/futex.rs)
  is an implementation reference, not a stable `std::sync::Mutex` backend
  contract. Match any implementation claim to the measured `rustc -Vv` release
  and that release's source revision.

## Placement: affinity, cpusets, and online central processing units (CPUs)

- [`sched_setaffinity(2)`](https://man7.org/linux/man-pages/man2/sched_setaffinity.2.html)
  defines affinity as a per-thread eligibility mask. Linux silently intersects
  the requested mask with processors present on the system and cpuset
  restrictions, and rejects a mask with no permitted processor. One-bit
  affinity does not reserve that logical CPU or exclude interrupts and other
  eligible tasks.
- [Control group v2](https://docs.kernel.org/admin-guide/cgroup-v2.html#cpuset)
  defines `cpuset.cpus` as the requested set and `cpuset.cpus.effective` as the
  online CPUs actually granted by the parent. Hotplug and ancestor changes can
  alter the effective set without changing the requested text.
- [Linux CPU topology export](https://docs.kernel.org/admin-guide/cputopology.html)
  distinguishes `online`, `present`, `possible`, and `offline` masks and maps
  architecture topology callbacks to `sysfs`. Missing or synthetic topology in
  a guest is not evidence that two logical CPUs do or do not share a core.

## Fair scheduling and implementation drift

- [Earliest Eligible Virtual Deadline First
  (EEVDF)](https://docs.kernel.org/scheduler/sched-eevdf.html) defines lag,
  eligibility, and virtual-deadline selection and states that Linux began the
  transition in 6.6. It does not imply that every 6.6-or-newer distribution has
  identical EEVDF code or tuning.
- [Completely Fair Scheduler (CFS) design
  notes](https://docs.kernel.org/scheduler/sched-design-CFS.html) document the
  earlier virtual-runtime model. They remain useful background but are not the
  exact selection algorithm for a current EEVDF implementation.
- [Upstream `kernel/sched/fair.c`](https://github.com/torvalds/linux/blob/master/kernel/sched/fair.c)
  is the implementation source for the upstream fair class, including weight,
  placement, wakeup, and load-balancing logic. Claims about a measured host
  require its exact kernel source or distribution patch set, not current main.
- [Extensible Scheduler Class
  (`sched_ext`)](https://docs.kernel.org/scheduler/sched-ext.html) can replace
  fair-class behavior for selected tasks only when the required kernel options
  are enabled and a Berkeley Packet Filter (BPF) scheduler is loaded. Record
  `/sys/kernel/sched_ext/state` and the loaded operations name before attributing
  behavior to EEVDF; kernel version alone is insufficient.

## Scheduling policies, fairness, and starvation

- [`sched(7)`](https://man7.org/linux/man-pages/man7/sched.7.html) defines Linux
  policy ordering: normal policies use nice values, first-in, first-out
  (`SCHED_FIFO`) has no time slice, round robin (`SCHED_RR`) adds a quantum, and
  `SCHED_DEADLINE` has separate reservation parameters. `SCHED_FIFO` progress
  lasts until block, preemption by a higher priority, or yield, so assigning it
  can starve lower classes.
- [Deadline task scheduling](https://docs.kernel.org/scheduler/sched-deadline.html)
  defines `runtime`, `deadline`, and `period`, Constant Bandwidth Server (CBS)
  throttling, and admission control. Admission protects reserved CPU bandwidth;
  it does not prove an application's worst-case execution time, lock bound, or
  end-to-end deadline.
- [Real-time group scheduling](https://docs.kernel.org/scheduler/sched-rt-group.html)
  documents real-time bandwidth controls and their configuration boundary.
  Throttling behavior depends on kernel configuration, cgroup mode, and current
  sysctls; it is not a portable starvation-prevention guarantee.

## Simultaneous multithreading (SMT) and isolation

- [x86 topology documentation](https://docs.kernel.org/arch/x86/topology.html)
  defines `topology_sibling_cpumask()` as the online hardware threads in one
  core. This identifies scheduler topology; it does not turn sibling logical
  CPUs into independent physical cores or quantify their shared capacity.
- [Linux CPU isolation](https://docs.kernel.org/admin-guide/cpu-isolation.html)
  separates task placement, scheduler-domain isolation, full dynticks
  (`nohz_full`), interrupt affinity, and managed interrupts. Isolation is a
  layered configuration; firmware interrupts, kernel entry, and unmovable work
  can still disturb a userspace thread.
- [Control group v2 isolated
  partitions](https://docs.kernel.org/admin-guide/cgroup-v2.html#cpuset-interface-files)
  remove scheduler load balancing and unbound workqueues from a valid isolated
  partition. They do not by themselves move device interrupts or reserve an
  entire simultaneous-multithreading (SMT) core.
- [Linux core scheduling](https://docs.kernel.org/admin-guide/hw-vuln/core-scheduling.html)
  coordinates which tasks may run concurrently on SMT siblings for trust-domain
  isolation. It is a security mechanism, not exclusive-core capacity or a
  per-thread latency bound.

## Vendor hardware boundaries

- [Intel 64 and IA-32 Optimization Reference Manual, volume 1, revision
  050](https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf)
  describes Intel Hyper-Threading resource sharing and model-specific
  optimization guidance. Apply a chapter only after matching the host's vendor,
  family, model, stepping, and enabled topology; it is not an x86-64 guarantee.
- [AMD EPYC SMT technology brief, April
  2025](https://www.amd.com/content/dam/amd/en/documents/epyc-business-docs/white-papers/amd-epyc-smt-technology-brief.pdf)
  describes two-way SMT and shared versus partitioned resources in AMD Zen 5
  EPYC processors. Its design and performance claims do not transfer to older
  Zen generations, Intel processors, or an unidentified guest CPU.
- [Arm's Neoverse utilization
  note](https://developer.arm.com/community/arm-community-blogs/b/servers-and-cloud-computing-blog/posts/reassess-cpu-utilization-on-x86-and-arm)
  states that the named Neoverse N-series and V-series processors do not
  implement SMT and explains why logical-CPU utilization is not equivalent to
  physical-core headroom on SMT systems. This is a product-family boundary, not
  an Arm instruction-set rule.

## Priority inversion and lock-holder progress

- [Linux real-time mutexes](https://docs.kernel.org/locking/rt-mutex.html) define
  transitive priority inheritance (PI): a lower-priority owner inherits a higher
  waiter's priority until unlock, and a blocked boosted owner can propagate the
  boost through another real-time mutex. Priority inheritance shortens
  scheduler-caused blocking; it does not shorten the owner's critical-section
  work or remove I/O, faults, interrupts, and longer dependency chains.
- [Linux priority-inheritance
  futexes](https://docs.kernel.org/locking/pi-futex.html) define the user-space
  atomic fast path and `FUTEX_LOCK_PI`/`FUTEX_UNLOCK_PI` slow path backed by an
  in-kernel real-time mutex. Ordinary futex wait/wake operations do not gain
  these semantics automatically.
- [POSIX `pthread_mutexattr_setprotocol`](https://pubs.opengroup.org/onlinepubs/9699919799/functions/pthread_mutexattr_setprotocol.html)
  defines `PTHREAD_PRIO_NONE`, `PTHREAD_PRIO_INHERIT`, and
  `PTHREAD_PRIO_PROTECT`. The protocol must be selected on the mutex; thread
  priority alone does not retrofit inheritance into an ordinary lock.
- [Rust's futex mutex implementation](https://github.com/rust-lang/rust/blob/main/library/std/src/sys/sync/mutex/futex.rs)
  uses an unlocked/locked/contended word with `futex_wait` and `futex_wake` for
  targets selecting that backend at that source revision. It does not invoke PI
  futex operations, so this implementation cannot be cited as priority-
  inheritance protection; Rust may change or select another backend by target
  and release.

## Scheduler and power observations

- [Scheduler statistics](https://docs.kernel.org/scheduler/sched-stats.html)
  defines versioned `/proc/schedstat` fields and says counters require baseline
  deltas. Parsers must check the exported version; configuration, symmetric
  multiprocessing (`CONFIG_SMP`), and format revisions control which fields
  exist.
- [The `sched_schedstats`
  sysctl](https://docs.kernel.org/admin-guide/sysctl/kernel.html#sched-schedstats)
  enables scheduler-stat collection and incurs overhead. An absent, disabled,
  or reset counter is not evidence that no scheduler delay occurred.
- [CPU idle management](https://docs.kernel.org/admin-guide/pm/cpuidle.html)
  defines idle-state target residency, exit latency, governor prediction, and
  per-state `sysfs` counters. A state request gives hardware permission to enter
  up to that state; it does not prove the physical state actually reached.
- [Power Management Quality of Service
  (PM QoS)](https://docs.kernel.org/power/pm_qos_interface.html) defines latency
  constraints aggregated across active requests. A request constrains governor
  selection while it remains active; it does not reserve CPU time or remove
  scheduler and interrupt delay.
- [CPU frequency scaling](https://docs.kernel.org/admin-guide/pm/cpufreq.html)
  defines policy domains, drivers, governors, and `sysfs` attributes.
  `scaling_cur_freq` is commonly the last requested performance state and may
  not be the hardware's instantaneous frequency.
- [`intel_pstate`](https://docs.kernel.org/admin-guide/pm/intel_pstate.html) and
  [`amd-pstate`](https://docs.kernel.org/admin-guide/pm/amd-pstate.html) define
  vendor-specific Linux performance-scaling drivers. Neither interface applies
  unless the measured host exposes that driver and the required processor and
  firmware support.
- [Amazon Elastic Compute Cloud (EC2) processor-state
  control](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/processor_state_control.html)
  documents provider-visible idle-state (C-state) and performance-state
  (P-state) controls only for supported instance and processor combinations. It
  does not imply that either required host exposes those controls or that a
  requested state equals delivered hardware residency or frequency.
