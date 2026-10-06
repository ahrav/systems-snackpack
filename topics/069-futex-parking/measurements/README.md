# Exact-source measurements

Measured source `35c6b5a00f0f761ccbf9a6bff6052610cd613358`. Both required hosts passed 4 unit tests, 1 doctest, 192 processes and standalone library/example Clippy with warnings denied. All six frozen input hashes passed before compilation, after measurement and after linting.

Raw evidence: `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-069/2026-10-06-35c6b5a0`. [Receipt](receipt.json) binds inputs, host facts and raw run hashes. Initial campaign is retained separately; its timer included worker readiness and is not pooled.

## Selection

Values are median wall nanoseconds per successful critical section, with interquartile range in brackets. The resolved winner must beat every alternative by at least 2% and have each paired 95% bootstrap median-ratio upper bound below 1. Otherwise retain unresolved. Eight process blocks are a small shared-host sample; intervals are descriptive and not adjusted for selecting across alternatives.

### arm

dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com. MIDR 0x411fd401; 64 available CPUs. 1.98.1 / LLVM 22.1.8. Kernel 6.12.110-135.202.amzn2023. Optimization 3, target-cpu=native. Full feature cfg and affinity are in retained host.txt/plan.json.

| Workload | Spin | Wake-one | Wake-all | Hybrid100 | Selection |
|---|---:|---:|---:|---:|---|
| uncontended | 27.53 [27.45,27.60] | 27.47 [27.45,27.54] | 27.51 [27.34,27.57] | 27.51 [27.44,27.56] | unresolved |
| short | 109.37 [99.76,128.34] | 177.38 [146.09,207.14] | 150.96 [142.42,172.60] | 162.50 [111.22,173.65] | unresolved |
| long | 678.26 [666.87,690.24] | 1021.00 [1011.04,1038.14] | 900.55 [887.01,912.86] | 783.49 [742.08,841.48] | spin |
| oversubscribed | 33.96 [33.83,34.05] | 33.93 [33.86,34.72] | 33.93 [33.84,33.97] | 33.88 [33.83,33.94] | unresolved |
| sleeping_owner | 103387.99 [103322.68,111841.73] | 104827.99 [104708.67,104921.78] | 106168.08 [106101.84,106432.75] | 104759.39 [104673.27,104843.55] | unresolved |
| burst | 12153.12 [10964.81,14034.50] | 13307.50 [12515.75,13659.50] | 13284.50 [11658.75,14526.31] | 12840.00 [11671.25,14122.06] | unresolved |

[Full paired intervals and CPU/wake counts](arm-summary.json).

### xxl

dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com. Intel Xeon Platinum 8488C; 192 available CPUs. 1.98.0 / LLVM 22.1.8. Kernel 6.12.110-135.202.amzn2023. Optimization 3, target-cpu=native. Full feature cfg and affinity are in retained host.txt/plan.json.

| Workload | Spin | Wake-one | Wake-all | Hybrid100 | Selection |
|---|---:|---:|---:|---:|---|
| uncontended | 22.31 [22.25,22.39] | 22.16 [22.10,22.22] | 22.33 [22.23,22.40] | 22.26 [22.19,22.33] | unresolved |
| short | 121.38 [105.53,142.04] | 91.69 [88.14,107.86] | 90.77 [88.61,105.97] | 170.78 [110.93,196.93] | unresolved |
| long | 254.35 [245.12,270.99] | 944.96 [907.30,959.96] | 978.79 [966.79,994.72] | 449.21 [422.42,461.13] | spin |
| oversubscribed | 28.34 [28.10,28.41] | 28.35 [28.12,28.51] | 28.23 [27.96,28.36] | 28.15 [28.04,28.46] | unresolved |
| sleeping_owner | 104541.31 [104368.43,106380.49] | 105374.30 [105270.41,105415.54] | 105680.99 [105523.99,105762.48] | 105406.88 [105381.64,105456.21] | unresolved |
| burst | 14740.25 [12673.50,15286.75] | 13548.38 [12245.62,14390.25] | 11369.75 [10492.56,12123.19] | 11961.25 [10926.00,12744.44] | unresolved |

[Full paired intervals and CPU/wake counts](xxl-summary.json).

## Interpretation

Spin is the resolved elapsed-time winner only for the four-worker 256-step arithmetic cell on both hosts. Other cells remain unresolved under the predeclared rule.

For a sleeping owner, Arm process CPU medians are 156.93 us/op (spin), 5.27 (one), 10.12 (all), 5.27 (hybrid). x86 is 192.82, 7.65, 9.45, 7.73 us/op. Wake-all returns 2.19 / 1.50 woken waiters per operation on Arm/x86, versus 0.75 for wake-one. This supports a CPU-budget reason for parking; it does not establish an elapsed-time winner or causal scheduler timeline.

The one-CPU case produces essentially no workload futex calls. Short quotas can execute serially; it does not reproduce owner preemption. Tiny bursts measure release/join and scheduling overhead in a warm process.

Exact acquire disassembly contains Arm casa/swpa/isb and x86 lock cmpxchg/xchg/pause plus slow-path policy-string checks. See retained code-inspection.md. No whole-process counter attribution, isolated ISA comparison, production-library ranking, cold-cache, fairness, or energy claim.
