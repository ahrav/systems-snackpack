# Frozen protocol

- Correct candidates: 1, 2, 4 workers, disjoint ordered output slices.
- Workloads: 64 and 4096 jobs; each performs 1,000,000 wrapping affine steps.
- Policies: no local quota, 50% CPU with 100 ms period, 50% with 10 ms period.
- Four distinct physical cores selected from current task affinity. This grants
  eligibility, not exclusive use. Default release build, no target-cpu=native.
- Six independent process blocks use all worker permutations. Policy order
  rotates and size order reverses on alternating blocks: 108 processes/host.
- One 16-job/1000-step warmup, then 200 ms sleep. Sleep does not synchronize
  quota phase. Each process gets a fresh service, so burst state matters.
- Timer includes output allocation, worker spawn, computation and joins. It
  excludes warmup, cgroup creation, oracle, printing and output destruction.
  launch_ns separately includes startup, warmup, sleep, validation and shutdown.
- Every output is checked with an affine-composition oracle in logarithmic
  work. Oracle, structural edge tests and counter-reset tests must pass.
- Primary selection: lowest median wall_ns, at least 5% median paired
  improvement, and all six paired wins against every rival. Otherwise unresolved.
  IQR uses inclusive quartiles. No production-tail or ISA-wide inference.
- cpu.stat and PSI reads bracket the timer sequentially and are not atomic.
  Their deltas include observation skew and can have short-window accounting
  effects. They corroborate enforcement and are not the selection objective.
- All config reads are before warmup. Temporary service membership and cgroup
  device/inode are checked across timing. Ancestor configuration is recorded;
  ancestor counter deltas and per-worker traces are not collected.
- Tiny output vectors do not deliberately exercise or measure memory.high, swap, reclaim or OOM.

The first initial runner assumed cpu.max existed in an uncapped service. It
failed before accepting timing rows. CPUWeight=100 explicitly enables the
controller for all policies. A pilot with shorter work was not pooled. Final
committed runs add workspace/analysis hashes and an explicit target directory;
Rust workload and timing boundary remain identical to the successful initial
experiment. The analyzer rejects incomplete matrices before naming a selection.
