# Topic 070 measured results

Measured source: `6719300145a9b640fa923eda3a88ca5afd2547e3`. Six independent process samples per candidate/cell.

All times below are batch wall milliseconds: median [inclusive IQR]. Selection requires at least 5% median paired improvement and all six paired wins over every rival. Unresolved is not proof of equality.

| Host | Policy | Jobs | 1 worker | 2 workers | 4 workers | Selected |
|---|---|---:|---:|---:|---:|---|
| arm | uncapped | 64 | 49.391 [49.370, 49.407] | 24.738 [24.730, 24.750] | 12.461 [12.446, 12.470] | unresolved |
| arm | uncapped | 4096 | 3155.714 [3155.468, 3155.748] | 1577.813 [1577.744, 1577.921] | 789.039 [788.998, 789.099] | 4 |
| arm | q100 | 64 | 49.375 [49.366, 49.387] | 24.748 [24.733, 24.760] | 12.461 [12.448, 12.471] | 4 |
| arm | q100 | 4096 | 6249.629 [6245.823, 6250.538] | 6238.688 [6194.143, 6243.127] | 6207.964 [6185.564, 6238.605] | unresolved |
| arm | q10 | 64 | 88.916 [85.342, 92.593] | 88.186 [77.918, 91.735] | 91.791 [91.116, 92.852] | unresolved |
| arm | q10 | 4096 | 6302.038 [6300.182, 6303.548] | 6301.588 [6296.628, 6304.218] | 6304.082 [6302.236, 6308.615] | unresolved |
| x86 | uncapped | 64 | 10.084 [10.079, 10.090] | 5.086 [5.079, 5.099] | 2.622 [2.597, 2.646] | 4 |
| x86 | uncapped | 4096 | 641.340 [641.255, 641.595] | 320.656 [320.640, 320.670] | 160.636 [160.585, 160.765] | 4 |
| x86 | q100 | 64 | 10.074 [10.066, 10.087] | 5.096 [5.088, 5.104] | 2.617 [2.611, 2.621] | 4 |
| x86 | q100 | 4096 | 1226.986 [1203.483, 1232.228] | 1173.211 [1167.116, 1193.938] | 1184.338 [1179.493, 1192.989] | unresolved |
| x86 | q10 | 64 | 11.866 [10.472, 13.111] | 11.885 [6.497, 14.246] | 14.663 [13.771, 19.611] | unresolved |
| x86 | q10 | 4096 | 1273.955 [1272.305, 1275.893] | 1275.240 [1270.011, 1279.196] | 1277.795 [1274.955, 1281.680] | unresolved |

q100 means cpu.max=50000 100000; q10 means 5000 10000. CPUWeight=100 for all services. All observed ancestor cpu.max settings were max. Host CPUs remain shared.

Arm: declared dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, aarch64, 64 available CPUs, ARM implementer0x41/part0xd40/r1p1 (MIDR0x411fd401), rustc1.98.1/LLVM22.1.8. xxl resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, x86_64, 192 available CPUs, Xeon Platinum8488C, rustc1.99.0/LLVM23.1.1. Both kernels6.12.110-135.202.amzn2023 and systemd252.23; four distinct cores0,1,2,3 eligible per process. Cargo release, default target features; no native CPU flag.

The linked Arm timed worker uses a dependent madd loop decrementing one step. The x86 timed worker uses composed constants with imul/add and decrements eight steps. This is observed generated code, not a universal ISA comparison. The oracle is outside timing.

Finite batch boundaries matter. Small q100 batches can finish before throttling. The q10 treatment interrupts those bursts sooner. Large quota batches have no resolved worker winner; a lower median alone does not satisfy the selection rule. Do not pool initial and final runs or compare hosts as if their compilers generated the same instruction workload.

CPU/PSI values bracket the timer through sequential reads; short-window accounting and skew make them corroboration rather than exact lost-time fractions. The large x86 q100 four-worker median aggregate throttle exceeds elapsed time. It aggregates delay and is not a wall-time percentage.

Limits: six process runs/cell, shared hosts, process-local warmup, fresh cgroup/batch, fixed arithmetic job, allocation/spawn/join included. No p99, persistent-pool, peer-impact, energy, memory-pressure, swap, OOM, or universal optimum claim. The memory buffer model in round notes is derived only.

Initial successful source ran108processes/host; the initial failed missing-controller pilot was rejected and retained. Final exact committed source separately ran108processes/host. All outputs passed the oracle. Seven workspace gates passed; native Linux Clippy results retained.

Raw evidence: /Users/ahrav/.codex/learning/advanced-systems-evidence/topic-070/2026-10-07-67193001. See receipt.json for source identities.
