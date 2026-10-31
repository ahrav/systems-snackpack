# Results: concurrent marking model

Measured source and harness: `2b2da8b9b13a9e0de01a2f017123321334b8c907`.
Source archive SHA-256: `800decd1fa87ea17e05ca907c4ac888f81811091b1af1f617c2d929f5565469f`.

Each host passed three unit tests, one doctest, 333,504 independent reachability comparisons, and exact workload scan/barrier/retention checks. Each ran 72 measured fresh processes and nine excluded warmups. Rust 1.93.1 release defaults on all hosts.

| Host | Workload | STW ms median [min,max] | Insertion ms median [min,max] | SATB ms median [min,max] | Pair findings |
|---|---|---|---|---|---|
| local | keep | 4.418 [4.062,4.855] | 3.261 [3.044,3.549] | 3.464 [3.220,3.668] | insertion faster than stw; satb faster than stw; insertion/satb unresolved |
| local | delete | 2.384 [2.243,2.611] | 2.537 [2.434,2.615] | 3.389 [3.304,3.613] | stw/insertion unresolved; stw faster than satb; insertion faster than satb |
| local | replace | 2.106 [2.033,2.197] | 2.584 [2.530,2.773] | 3.448 [3.414,3.527] | stw faster than insertion; stw faster than satb; insertion faster than satb |
| arm | keep | 9.218 [9.116,9.426] | 13.594 [13.399,13.652] | 14.019 [13.945,14.351] | stw faster than insertion; stw faster than satb; insertion/satb unresolved |
| arm | delete | 5.688 [5.599,5.873] | 6.037 [5.919,6.166] | 13.945 [13.735,14.190] | stw/insertion unresolved; stw faster than satb; insertion faster than satb |
| arm | replace | 5.672 [5.584,7.736] | 6.466 [6.383,6.650] | 14.420 [14.235,14.626] | stw/insertion unresolved; stw faster than satb; insertion faster than satb |
| x86 | keep | 7.934 [7.874,8.029] | 11.130 [11.054,11.287] | 11.451 [11.388,11.795] | stw faster than insertion; stw faster than satb; insertion/satb unresolved |
| x86 | delete | 4.173 [4.162,4.254] | 4.484 [4.460,4.879] | 11.378 [11.325,11.642] | stw/insertion unresolved; stw faster than satb; insertion faster than satb |
| x86 | replace | 4.592 [4.395,4.705] | 4.967 [4.856,5.034] | 11.572 [11.428,11.839] | stw faster than insertion; stw faster than satb; insertion faster than satb |

Eight paired blocks; faster requires every block to exceed 5%. Tie requires every pair within 5%; otherwise unresolved. These are descriptive comparisons, with no population confidence bound. Raw samples are retained in `evidence/*.json`.

Per cycle, keep scans and retains 16,384 objects for every policy. Delete and replace scan/retain one object for STW and insertion, and 16,384 for SATB. Insertion and SATB each execute 16,384 barrier calls; STW executes zero. SATB preserves its initial-snapshot contract and pays additional retention and scanning in these schedules.

Measured wall time includes graph allocation/validation, model metadata, stores, marking and destruction. The models run sequentially with deterministic interleaving. Production pause latency, allocation assists, real concurrency, weak-memory behavior, bandwidth contention and actual collector throughput remain unmeasured.

Linux hosts use CPU 0 affinity. Frequency, host load, thermals and SMT are uncontrolled. Local CPU affinity is uncontrolled. Local CPU model is unavailable because the sandbox denied sysctl; uname reports macOS arm64. That initial metadata failure occurred before testing/timing, was retained, and the local run succeeded after omitting the denied query. Host kernels and Linux CPU identities are retained in host logs.

Preliminary uncommitted measurements were excluded. The source was corrected for one Clippy collapsible-if finding before final campaigns. A wrong-directory Cargo invocation failed during preparation; final commands ran from the worktree or archive root.

Full-workspace validation is recorded in validation.md. Sources and scope are in README.md and sources.md.
