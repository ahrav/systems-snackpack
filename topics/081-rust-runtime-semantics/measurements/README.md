# Topic 81 measurements

Measured source: `20943800b169eaa04eab2f55c2bbdabc9de88a44`. Both Linux hosts used the exact hash-verified Git archive.

Each host passed six unit tests, two compile-fail doctests, 390 independent Python oracle cases, unwind/abort subprocess probes, and every timed checksum. Each ran 20 calibration, 20 warmup, and 120 measured processes.

Rust 1.93.1 / LLVM 21.1.8, opt-level=3, target-cpu=native, one codegen unit, LTO off, panic unwind. CPU 0 affinity; shared hosts, no exclusive reservation or frequency lock. The Arm host reports AArch64 (64 single-threaded cores); xxl resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, verified x86_64, Xeon Platinum 8488C, KVM.

The timer covers repeated batch calls and checksum accumulation. Allocation, process startup, independent checks, and output are outside it. Runtime parameters and slices pass through black_box; the per-batch outer functions remain inspectable. Inputs are reused and warm. Addition and multiply/rotate/xor each use one policy per batch. The 8192-element dispatch input is 64 KiB; dot products read two such inputs.

Each cell uses common calibrated repetitions. Six blocks alternate cyclic order and its reverse. Values below are median [minimum, maximum] ns per element across six processes. Warmups and calibration are excluded.

The descriptive rule calls A faster than B only if every paired B/A ratio exceeds 1.05; a practical tie requires every ratio in [1/1.05, 1.05]. Other cells are unresolved. This is a small-sample decision rule, not a confidence interval or equivalence test.

## Dispatch results

| Host | Policy | Items | Generic | Enum | Dynamic per item | Dynamic per batch |
|---|---|---:|---:|---:|---:|---:|
| arm | add | 32 | 0.1716 [0.1712, 0.1723] | 0.1820 [0.1813, 0.1822] | 1.0092 [1.0060, 1.0110] | 0.2020 [0.2006, 0.2036] |
| arm | add | 8192 | 0.1939 [0.1938, 0.1943] | 0.1932 [0.1930, 0.1945] | 0.7744 [0.7738, 0.7755] | 0.1933 [0.1930, 0.1952] |
| arm | mix | 32 | 0.6433 [0.5182, 0.7023] | 0.5284 [0.5224, 0.5386] | 1.3739 [1.3703, 1.3809] | 0.5314 [0.5273, 0.5446] |
| arm | mix | 8192 | 0.2936 [0.2935, 0.2941] | 0.2932 [0.2907, 0.2938] | 1.1011 [1.0967, 1.1062] | 0.2932 [0.2907, 0.2947] |
| xxl | add | 32 | 0.1317 [0.1315, 0.1325] | 0.1419 [0.1417, 0.1429] | 1.6393 [1.6388, 1.6416] | 0.1417 [0.1417, 0.1444] |
| xxl | add | 8192 | 0.0865 [0.0864, 0.0868] | 0.0868 [0.0867, 0.0870] | 1.5703 [1.5684, 1.5719] | 0.0867 [0.0866, 0.0870] |
| xxl | mix | 32 | 0.2650 [0.2650, 0.2663] | 0.2654 [0.2651, 0.2658] | 1.9537 [1.9525, 1.9558] | 0.2749 [0.2748, 0.2754] |
| xxl | mix | 8192 | 0.2063 [0.2063, 0.2072] | 0.2068 [0.2064, 0.2075] | 1.8862 [1.8842, 1.8905] | 0.2066 [0.2065, 0.2073] |

## Bounds comparison

| Host | Items | Index | Zip | Paired outcome |
|---|---:|---:|---:|---|
| arm | 32 | 0.2514 [0.2469, 0.2550] | 0.2433 [0.2396, 0.2479] | unresolved |
| arm | 8192 | 0.2077 [0.2072, 0.2108] | 0.2078 [0.2074, 0.2093] | practical tie |
| xxl | 32 | 0.2638 [0.2635, 0.2668] | 0.2636 [0.2631, 0.2639] | practical tie |
| xxl | 8192 | 0.2150 [0.2129, 0.2160] | 0.2143 [0.2123, 0.2157] | practical tie |

## Findings and limits

- Per-item dynamic dispatch loses to each other implementation in all eight dispatch cells under the six-pair rule.
- Small addition batches favor generic code on both hosts. On Arm, enum also beats batch dispatch; on x86 those two tie.
- Large addition and multiply/rotate batches tie among generic, enum, and batch dispatch on both hosts. Small x86 multiply/rotate also ties among those three.
- Small Arm multiply/rotate has generic timings from 0.5182 to 0.7023 ns/item. Its comparisons against enum and batch dispatch remain unresolved; enum and batch dispatch tie. The variation is retained, not discarded or assigned an unmeasured cause.
- Indexed versus zipped dot products tie in three cells. Arm at 32 items remains unresolved under the declared rule. No unsafe replacement is justified by this comparison.

Linked code inspection: dyn_item contains `blr x23` in the Arm element loop and `call *%r13` in the x86 element loop. dyn_batch makes a single indirect tail transfer (`br x4` / `jmp *%rax`) to the concrete batch method. Concrete loops contain vector instructions (SVE on this Arm build; vector integer operations on this x86 build). Both dot kernels retain the entry length assertion but have no per-element bounds-panic path; their vector/scalar tail branches remain.

The retained calls and vectorized alternatives support an explanation involving both dispatch and optimization visibility. Timings do not isolate indirect-call latency, SIMD benefit, or CPU architecture causality. There are no PMU measurements, mixed-policy objects, cold-cache runs, multi-thread contention, production tail latency, or code-size treatment. Native builds differ by host ISA. No host-wide or universal winner is claimed.

## All paired comparisons

| Host | Policy | Items | A | B | B/A min, median, max | Outcome |
|---|---|---:|---|---|---:|---|
| arm | add | 32 | generic | enum | 1.055, 1.061, 1.064 | generic faster |
| arm | add | 32 | generic | dyn-item | 5.851, 5.877, 5.907 | generic faster |
| arm | add | 32 | generic | dyn-batch | 1.169, 1.176, 1.188 | generic faster |
| arm | add | 32 | enum | dyn-item | 5.527, 5.550, 5.554 | enum faster |
| arm | add | 32 | enum | dyn-batch | 1.102, 1.110, 1.121 | enum faster |
| arm | add | 32 | dyn-item | dyn-batch | 0.199, 0.200, 0.202 | dyn-batch faster |
| arm | add | 8192 | generic | enum | 0.995, 0.997, 1.001 | practical tie |
| arm | add | 8192 | generic | dyn-item | 3.981, 3.994, 4.001 | generic faster |
| arm | add | 8192 | generic | dyn-batch | 0.994, 0.997, 1.007 | practical tie |
| arm | add | 8192 | enum | dyn-item | 3.978, 4.009, 4.011 | enum faster |
| arm | add | 8192 | enum | dyn-batch | 0.993, 1.000, 1.011 | practical tie |
| arm | add | 8192 | dyn-item | dyn-batch | 0.249, 0.250, 0.252 | dyn-batch faster |
| arm | mix | 32 | generic | enum | 0.744, 0.824, 1.039 | unresolved |
| arm | mix | 32 | generic | dyn-item | 1.959, 2.147, 2.644 | generic faster |
| arm | mix | 32 | generic | dyn-batch | 0.751, 0.829, 1.029 | unresolved |
| arm | mix | 32 | enum | dyn-item | 2.544, 2.600, 2.634 | enum faster |
| arm | mix | 32 | enum | dyn-batch | 0.990, 1.002, 1.035 | practical tie |
| arm | mix | 32 | dyn-item | dyn-batch | 0.384, 0.386, 0.397 | dyn-batch faster |
| arm | mix | 8192 | generic | enum | 0.990, 0.998, 1.001 | practical tie |
| arm | mix | 8192 | generic | dyn-item | 3.734, 3.750, 3.768 | generic faster |
| arm | mix | 8192 | generic | dyn-batch | 0.991, 0.999, 1.002 | practical tie |
| arm | mix | 8192 | enum | dyn-item | 3.751, 3.756, 3.776 | enum faster |
| arm | mix | 8192 | enum | dyn-batch | 0.990, 1.001, 1.008 | practical tie |
| arm | mix | 8192 | dyn-item | dyn-batch | 0.264, 0.266, 0.268 | dyn-batch faster |
| arm | dot | 32 | index | zip | 0.947, 0.967, 1.004 | unresolved |
| arm | dot | 8192 | index | zip | 0.992, 1.000, 1.004 | practical tie |
| xxl | add | 32 | generic | enum | 1.070, 1.079, 1.079 | generic faster |
| xxl | add | 32 | generic | dyn-item | 12.374, 12.450, 12.480 | generic faster |
| xxl | add | 32 | generic | dyn-batch | 1.070, 1.077, 1.096 | generic faster |
| xxl | add | 32 | enum | dyn-item | 11.475, 11.559, 11.572 | enum faster |
| xxl | add | 32 | enum | dyn-batch | 0.992, 0.999, 1.016 | practical tie |
| xxl | add | 32 | dyn-item | dyn-batch | 0.086, 0.086, 0.088 | dyn-batch faster |
| xxl | add | 8192 | generic | enum | 1.000, 1.002, 1.005 | practical tie |
| xxl | add | 8192 | generic | dyn-item | 18.079, 18.152, 18.174 | generic faster |
| xxl | add | 8192 | generic | dyn-batch | 0.998, 1.002, 1.005 | practical tie |
| xxl | add | 8192 | enum | dyn-item | 18.074, 18.089, 18.113 | enum faster |
| xxl | add | 8192 | enum | dyn-batch | 0.996, 0.999, 1.004 | practical tie |
| xxl | add | 8192 | dyn-item | dyn-batch | 0.055, 0.055, 0.055 | dyn-batch faster |
| xxl | mix | 32 | generic | enum | 0.996, 1.001, 1.003 | practical tie |
| xxl | mix | 32 | generic | dyn-item | 7.342, 7.368, 7.380 | generic faster |
| xxl | mix | 32 | generic | dyn-batch | 1.034, 1.037, 1.037 | practical tie |
| xxl | mix | 32 | enum | dyn-item | 7.352, 7.365, 7.372 | enum faster |
| xxl | mix | 32 | enum | dyn-batch | 1.034, 1.036, 1.038 | practical tie |
| xxl | mix | 32 | dyn-item | dyn-batch | 0.141, 0.141, 0.141 | dyn-batch faster |
| xxl | mix | 8192 | generic | enum | 0.998, 1.002, 1.006 | practical tie |
| xxl | mix | 8192 | generic | dyn-item | 9.092, 9.140, 9.165 | generic faster |
| xxl | mix | 8192 | generic | dyn-batch | 0.996, 1.001, 1.005 | practical tie |
| xxl | mix | 8192 | enum | dyn-item | 9.091, 9.116, 9.157 | enum faster |
| xxl | mix | 8192 | enum | dyn-batch | 0.996, 1.000, 1.003 | practical tie |
| xxl | mix | 8192 | dyn-item | dyn-batch | 0.109, 0.110, 0.110 | dyn-batch faster |
| xxl | dot | 32 | index | zip | 0.988, 0.998, 1.002 | practical tie |
| xxl | dot | 8192 | index | zip | 0.987, 0.994, 1.010 | practical tie |
