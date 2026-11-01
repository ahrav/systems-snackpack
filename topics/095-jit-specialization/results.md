# Topic 095 measurements

Measured source and runner: `ce874cce601335b4f0e7295ab3c7f23d8d61fff3`.
Archive SHA-256: `531720c9ceb563870029d189507afc0a4f2b0c069ad0ba6b55fd1030cb111b22`.
Three unit tests, one doctest, and 55,987 independent Python oracle comparisons
passed on local macOS arm64 and both required Linux hosts. The oracle compares
exact sum, complete effect order, and earliest failed precondition. Node checks
all warmup results and the closed-form expected checksum in each process.

## Controls and scope

Default V8 and `--jitless` execute identical committed JavaScript. Each workload
has six paired fresh-process blocks, alternating order. Each process uses 8,192
rows, one cold call, 128 warmup calls, one post-warmup call, and 256 timed calls.
Stable uses layout A, shift trains A then measures B, and mixed alternates A/B
throughout. Values and checksum are identical across layouts. Sum bounds remain
inside signed 32-bit range in the JavaScript benchmark; Rust tests cover overflow.

Default wins a metric only when every paired default sample is below 0.95
times its jitless partner (`t_default < 0.95 * t_jitless`) in all six blocks;
jitless uses the reciprocal rule. A tie requires
`|t_default - t_jitless| <= 0.05 * max(t_default, t_jitless)` in every block.
Other outcomes are unresolved. These descriptive rules supply no population
confidence intervals. Every attempt is retained, including the slow local
stable whole-process sample. No timing samples were discarded.

Steady-loop timing excludes allocation and warmup but includes loop execution
and any ongoing optimization. Every workload allocates both row arrays before
the cold call; the separate stable traces on both hosts show `makeB` and its
`Array.from` mapper compiled concurrently on Maglev immediately before `sumRows`,
so default-mode cold-call timing includes background compiler work that
`--jitless` has no equivalent for. Whole-process timing includes startup, allocation,
all calls, assertions, output and shutdown. Trace runs are separate and excluded
from timing tables. Default versus jitless combines the effect of multiple
execution tiers. Neither comparison isolates compile time or recovery cost.

Local CPU model: unavailable because sysctl access was denied.
Local: macOS 26.7.2 arm64, Node 24.22.0, V8 13.6.233.17-node.57, affinity unpinned.
xxl: Linux 6.12.113-138.209.amzn2023 x86_64, Intel Xeon Platinum 8488C,
Node 24.22.2, V8 13.6.233.17-node.63, all child threads inherit CPU 0 affinity.
Rust correctness uses repository-pinned 1.93.1 on all three hosts.
CPU frequency, thermals, load and SMT contention are uncontrolled. Host Node/V8
versions differ; compare modes within each host and avoid ISA-wide conclusions.
CPU pinning also constrains background compilation threads and affects the result.

Arm host `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`: Linux aarch64,
correctness passed. Node was absent from PATH and checked local/nvm/opt/system
locations. The first location check encountered zsh unmatched-glob handling;
the corrected bounded check found no executable. V8 timing remains unavailable.
Remaining action: run the retained exact-source Node campaign on this host once
a Node executable is available, recording its version and full raw output.

## Measurements

Values are milliseconds: median [minimum, maximum].

| Host | Workload | Phase | Default | Jitless | Lower-time result |
|---|---|---|---|---|---|
| local | stable | coldNs | 0.223 [0.171, 0.410] | 0.180 [0.169, 0.184] | unresolved |
| local | stable | transitionNs | 0.009 [0.006, 0.009] | 0.131 [0.127, 0.132] | default |
| local | stable | steadyNs | 1.557 [1.449, 2.041] | 33.035 [32.372, 35.600] | default |
| local | stable | wallNs | 61.046 [56.667, 239.477] | 110.802 [106.179, 126.151] | unresolved |
| local | shift | coldNs | 0.231 [0.141, 0.464] | 0.180 [0.147, 0.226] | unresolved |
| local | shift | transitionNs | 0.133 [0.114, 0.327] | 0.155 [0.145, 0.191] | unresolved |
| local | shift | steadyNs | 2.460 [2.057, 2.972] | 33.640 [33.223, 34.210] | default |
| local | shift | wallNs | 53.160 [42.915, 75.831] | 109.837 [95.918, 124.030] | default |
| local | mixed | coldNs | 0.214 [0.186, 0.520] | 0.191 [0.149, 0.213] | unresolved |
| local | mixed | transitionNs | 0.009 [0.008, 0.010] | 0.135 [0.132, 0.137] | default |
| local | mixed | steadyNs | 1.859 [1.683, 2.249] | 34.373 [34.145, 45.383] | default |
| local | mixed | wallNs | 51.646 [45.652, 61.345] | 113.135 [100.485, 143.091] | default |
| xxl | stable | coldNs | 1.641 [1.349, 1.730] | 0.250 [0.239, 0.256] | jitless |
| xxl | stable | transitionNs | 0.011 [0.011, 0.011] | 0.198 [0.189, 0.206] | default |
| xxl | stable | steadyNs | 2.909 [2.762, 3.037] | 50.036 [49.288, 50.514] | default |
| xxl | stable | wallNs | 36.310 [35.316, 40.542] | 112.118 [109.851, 114.614] | default |
| xxl | shift | coldNs | 1.450 [0.410, 1.614] | 0.247 [0.241, 0.257] | jitless |
| xxl | shift | transitionNs | 1.197 [0.246, 1.216] | 0.216 [0.208, 0.222] | jitless |
| xxl | shift | steadyNs | 3.408 [3.305, 9.094] | 51.990 [51.594, 53.206] | default |
| xxl | shift | wallNs | 36.708 [35.299, 43.073] | 114.219 [112.603, 116.444] | default |
| xxl | mixed | coldNs | 1.546 [0.498, 1.920] | 0.258 [0.256, 0.265] | jitless |
| xxl | mixed | transitionNs | 0.012 [0.012, 0.039] | 0.220 [0.205, 0.234] | default |
| xxl | mixed | steadyNs | 3.141 [3.071, 5.569] | 53.548 [52.584, 54.786] | default |
| xxl | mixed | wallNs | 38.426 [35.016, 41.994] | 117.931 [116.438, 119.872] | default |

Default wins the 256-call phase for all three workloads on both measured hosts.
On xxl, jitless wins every cold-call comparison and the first call after the
shape change. Default wins whole-process time on xxl for all workloads. On
macOS, cold-call results and the shifted first call are unresolved; whole-process
stable is also unresolved because the observed ranges overlap across pairs.
No cell meets the strict tie rule.

Both hosts' separate shift traces report `sumRows` deoptimization with reason
`wrong map`, then compilation of `sumRows` again. xxl additionally reports
`prepare for on stack replacement (OSR)` bailouts in stable, shift and mixed.
A bailout count alone therefore does not identify failed input-shape assumptions.
Logging supports an observed mechanism; it does not measure that event's
standalone cost in the uninstrumented samples.

The Rust model tests recovery state, with layout A and signed 32-bit sum guards.
It emits no native code. Actual object materialization, GC root reconstruction,
exceptions, nested inlined frames, concurrent invalidation, and machine-register
maps remain outside its tested scope. Application tail percentiles, energy,
code-cache use, and standalone compilation/deoptimization costs are unmeasured.

## Validation provenance

Initial preparation invoked Cargo from the projectless directory and stopped
before compilation. A later local Node invocation in the repository had no Node
on PATH. Final runs use an explicit executable path and the committed archive.
Git's existing CodeDefender integration printed a denied log-file-open warning;
Git operations completed without changing hooks or platform controls.

Repository logs normalize trailing whitespace; original-byte hashes accompany
them. Original logs and source archives remain in the standalone deliverable.
`run.py` writes one `<workload>-<block>-<mode>.stderr` file per measured
process; each host's 36 files are committed as one `evidence/<host>/stderr.json`
object keyed by file name, and every value is the empty string.
