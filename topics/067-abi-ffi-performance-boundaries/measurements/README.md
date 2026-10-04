# Exact committed-source Linux results

Source commit `9f7214ad71eceb2dc613ee6e8ac84e48beff9190`; path-limited transferred archive SHA256 `9c5df96efbbcb0eebc888ced9fc5fe03f67793d60608927200a0babec11a9340`. All six source/runner hashes match both hosts. Full raw process evidence, binaries, generated code, transfer receipts and replay source are retained outside Git at `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-067/2026-10-04-9f7214ad`.

Both hosts passed four unit tests, one doctest and400 process checksums each. Initial scratch also passed400 processes per host; final results below govern selection. All seven local workspace gates passed. No concurrent task-owned builds/measurements on a measurement host. Shared-host load and frequency were not controlled.

Timing is reused-input steady state. Copy includes allocation, copy and release. Input generation, oracle, process startup and calibration are outside timing. First-after-check is warm, not cold. See [frozen design](../EXPERIMENT.md).

## arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com

`aarch64`, kernel `6.12.110-135.202.amzn2023.aarch64`, CPU `0x00000000411fd401`, 64 available logical CPUs; pinned CPU0. rustc 1.98.1 (48a229cea 2026-09-01); cc (GCC) 11.5.0 20240719 (Red Hat 11.5.0-5). Rust `-C target-cpu=native -C lto=off`; C `-std=c11 -O3 -fno-lto -Wall -Wextra -Werror -mcpu=native`; static C archive. LLVM versions are in receipt. This is not an architecture-family comparison.

Cells: median[min,max] microseconds/request across10 process blocks. Lowest median is shown when unresolved.

|N|rounds|Rust|scalar C|chunk256 C|batch C|copy C|Selection|
|---:|---:|---:|---:|---:|---:|---:|---|
|1|0|0.00443[0.00441,0.00444]|0.00413[0.00409,0.00433]|0.00456[0.00449,0.00460]|0.00435[0.00432,0.00440]|0.01971[0.01960,0.01986]|unresolved (scalar lowest)|
|1|16|0.01311[0.01296,0.01334]|0.01302[0.01300,0.01303]|0.01369[0.01367,0.01376]|0.01334[0.01333,0.01341]|0.03191[0.03165,0.03209]|unresolved (scalar lowest)|
|31|0|0.01032[0.01029,0.01037]|0.03286[0.03269,0.03309]|0.03930[0.03928,0.03936]|0.03853[0.02588,0.03858]|0.05389[0.04688,0.05531]|rust|
|31|16|0.26515[0.26302,0.26681]|0.30154[0.30025,0.30257]|0.27379[0.27100,0.27714]|0.27449[0.27240,0.27625]|0.29202[0.29015,0.29265]|rust|
|4096|0|0.39074[0.38994,0.39278]|3.16449[3.16353,3.17577]|3.37849[3.37650,3.39509]|3.16997[3.16938,3.20196]|3.71893[3.69881,3.73654]|rust|
|4096|16|34.69622[34.61834,34.80552]|38.45326[38.29885,38.68008]|35.83017[35.79951,36.02084]|35.87252[35.74157,35.91037]|36.36621[36.33044,36.59114]|rust|
|1048576|0|187.49811[187.17064,189.54448]|808.83200[808.18962,814.37100]|864.43116[863.50013,868.51694]|810.61469[808.14581,830.38819]|1059.59425[1057.68319,1062.36494]|rust|
|1048576|16|8692.37425[8606.49750,8738.10300]|9738.27975[9635.77550,9818.12650]|9174.96100[9168.50900,9205.48050]|9140.88775[9052.92900,9205.90800]|9421.06800[9379.54750,9499.66300]|rust|

## xxl: dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com

`x86_64`, kernel `6.12.110-135.202.amzn2023.x86_64`, CPU `Intel Xeon Platinum 8488C`, 192 available logical CPUs; pinned CPU0. rustc 1.98.0 (88d9e12ae 2026-08-18); cc (GCC) 11.5.0 20240719 (Red Hat 11.5.0-5). Rust `-C target-cpu=native -C lto=off`; C `-std=c11 -O3 -fno-lto -Wall -Wextra -Werror -march=native`; static C archive. LLVM versions are in receipt. This is not an architecture-family comparison.

Cells: median[min,max] microseconds/request across10 process blocks. Lowest median is shown when unresolved.

|N|rounds|Rust|scalar C|chunk256 C|batch C|copy C|Selection|
|---:|---:|---:|---:|---:|---:|---:|---|
|1|0|0.00336[0.00318,0.00347]|0.00409[0.00394,0.00421]|0.00442[0.00432,0.00455]|0.00379[0.00364,0.00389]|0.01742[0.01710,0.01766]|rust|
|1|16|0.01179[0.01177,0.01181]|0.01436[0.01434,0.01442]|0.01524[0.01520,0.01530]|0.01442[0.01439,0.01448]|0.02578[0.02572,0.02589]|rust|
|31|0|0.00884[0.00853,0.00922]|0.05168[0.05162,0.05192]|0.02464[0.02356,0.03101]|0.02403[0.02324,0.02579]|0.03691[0.03607,0.03792]|rust|
|31|16|0.31344[0.31310,0.31414]|0.38833[0.38781,0.40312]|0.37026[0.36895,0.37146]|0.36083[0.35967,0.36316]|0.37643[0.37567,0.37754]|rust|
|4096|0|0.19111[0.19057,0.19145]|6.43696[6.43331,6.46058]|2.74219[2.73453,2.75865]|2.59199[2.58101,2.92304]|3.40661[3.37225,3.61725]|rust|
|4096|16|41.33671[41.24357,41.47659]|50.59359[50.49055,50.66262]|48.94269[48.82627,49.24162]|47.05614[46.93787,47.31923]|48.30632[47.80924,49.15598]|rust|
|1048576|0|267.47898[267.08087,269.93647]|1645.45025[1643.97712,1649.25013]|717.87447[698.75831,781.41169]|723.52509[544.34181,747.89550]|1288.24281[1234.86900,1333.40625]|rust|
|1048576|16|10651.43950[10636.89500,10671.13900]|13192.88100[13161.64300,13250.18400]|12612.46100[12533.50100,12633.68000]|12650.93950[12588.71700,12735.70400]|13184.25050[13119.89600,13256.65200]|rust|

## Selection and evidence boundaries

Rust wins all eight x86 cases and the six Arm cases with at least31 values. Both single-value Arm cases are unresolved; scalar C has the lowest median. The initial single-value zero-round Arm scalar win did not survive final uncertainty, while initial31-value16-round Arm uncertainty resolved in the final run. No rerun was chosen to manufacture a winner.

The fixed rule requires every competitor/winner paired-ratio interval lower endpoint >1.02. Each interval is the2nd/9th order statistic of10 process pairs (97.85% marginal coverage under independent continuous pairs). Workloads and comparisons are multiple; selection is not a simultaneous confidence claim or proof of equality for unresolved cases. All intervals/ranges are in the compact summaries.

Exact final generated code retains Arm bl calls to topic67_one/topic67_batch. x86 calls use registers/GOT entries with relative relocations to those symbols. Rust zero-round reduction contains Arm SVE add/uaddv and x86 ymm vpaddq; the GCC C batch has scalar loops and a per-item rounds test on both hosts. Copy path retains allocation, memcpy, C call and deallocation. These shapes are observed; no counter experiment apportions the measured gain between vectorization, loop shape and calls. This experiment does not compare languages or pure ABI overhead.

No cold-cache, managed-runtime, callback, dynamic-link, asynchronous arrival-delay, production-tail or cross-language LTO result is claimed. The best tested native Rust option is useful only when moving the operation into Rust is an admissible interface choice. C-only choices remain workload/build dependent; no unmeasured universal optimum is claimed.
