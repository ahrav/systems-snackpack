# Topic 086: measurements

Measured source: `6c20563db07c983155ba4c7bb6247d92bbda9d7a`. Rust 1.93.1 / LLVM 21.1.8, native opt3, one CGU, LTO off, unwind. `src/lib.rs`, `src/main.rs` and `scripts/build.sh`'s compiler flags retain the measured bytes recorded in each host's `hashes.txt`. Later review commits make `run.py` refuse an existing campaign directory, record the inherited affinity mask, and validate affinity and probe output under `python -O`, make `build.sh` change to the topic directory, and replace `assert` checks in `analyze.py` and `oracle.py` with validation that survives `python -O` (finite positive timings, closed-form totals, the 16/8/4 repeat schedule, the six block orders, A/A rows ordered by declared position); the committed analyzer reproduces each host's `summary.json` byte for byte from its retained `raw.csv`.

Both required Linux hosts completed five Rust tests, 378 independent oracle cases / 10,719 checked values, 162 measured processes and two A/A processes. Each measurement process verifies every final output against a closed-form triangular-number oracle.

The serial column repeats a one-thread baseline for each worker-count cell. Parallel columns create the requested number of threads in each of two waves, because every measured n is a multiple of its worker count. The coordinator is separate. The fixed design is in [design.md](design.md).

## Arm Linux

| n | workers | serial ns/item, median [min,max] | local/add | totals/rescan | Pair decisions: serial/local; serial/rescan; local/rescan |
|---:|---:|---:|---:|---:|---|
| 4,096 | 1 | 0.389 [0.389,0.389] | 14.140 [13.742,14.485] | 13.892 [13.685,15.136] | serial; serial; unresolved |
| 4,096 | 4 | 0.389 [0.389,0.389] | 32.296 [31.622,33.209] | 32.001 [31.090,33.298] | serial; serial; tie |
| 4,096 | 8 | 0.389 [0.388,0.390] | 57.626 [56.442,59.051] | 56.817 [56.204,59.199] | serial; serial; tie |
| 262,144 | 1 | 0.418 [0.407,0.434] | 1.031 [1.016,1.075] | 0.857 [0.846,0.934] | serial; serial; rescan |
| 262,144 | 4 | 0.425 [0.394,0.449] | 0.694 [0.649,0.762] | 0.670 [0.653,0.702] | serial; serial; unresolved |
| 262,144 | 8 | 0.403 [0.386,0.487] | 1.092 [1.028,1.118] | 1.038 [0.988,1.373] | serial; serial; unresolved |
| 4,194,304 | 1 | 0.408 [0.404,0.426] | 0.740 [0.727,0.776] | 0.705 [0.699,0.757] | serial; serial; unresolved |
| 4,194,304 | 4 | 0.405 [0.402,0.408] | 0.226 [0.218,0.237] | 0.223 [0.208,0.239] | local; rescan; unresolved |
| 4,194,304 | 8 | 0.408 [0.404,0.412] | 0.195 [0.192,0.203] | 0.188 [0.183,0.193] | local; rescan; unresolved |

A/A ratio: 0.941. Same binary, path, settings and correct output; two points are not a null-calibration experiment or a noise floor.

## x86-64 Linux (xxl)

| n | workers | serial ns/item, median [min,max] | local/add | totals/rescan | Pair decisions: serial/local; serial/rescan; local/rescan |
|---:|---:|---:|---:|---:|---|
| 4,096 | 1 | 0.317 [0.317,0.318] | 13.861 [12.742,20.741] | 13.325 [12.374,14.260] | serial; serial; unresolved |
| 4,096 | 4 | 0.317 [0.317,0.318] | 34.557 [32.730,36.439] | 34.651 [32.301,36.651] | serial; serial; tie |
| 4,096 | 8 | 0.317 [0.317,0.318] | 64.349 [62.154,66.901] | 62.194 [60.946,64.262] | serial; serial; unresolved |
| 262,144 | 1 | 0.565 [0.530,0.733] | 1.278 [1.248,3.303] | 1.131 [0.941,1.261] | serial; serial; unresolved |
| 262,144 | 4 | 0.544 [0.536,0.757] | 0.797 [0.757,0.902] | 0.706 [0.684,0.734] | unresolved; unresolved; rescan |
| 262,144 | 8 | 0.585 [0.526,0.715] | 1.142 [1.076,1.874] | 1.171 [1.095,1.257] | serial; serial; unresolved |
| 4,194,304 | 1 | 0.726 [0.679,0.743] | 1.780 [1.453,1.992] | 1.685 [1.396,1.994] | serial; serial; unresolved |
| 4,194,304 | 4 | 0.718 [0.657,0.744] | 0.360 [0.345,0.390] | 0.318 [0.261,0.416] | local; rescan; unresolved |
| 4,194,304 | 8 | 0.668 [0.635,0.688] | 0.214 [0.208,0.247] | 0.229 [0.195,0.257] | local; rescan; unresolved |

A/A ratio: 1.215. Same binary, path, settings and correct output; two points are not a null-calibration experiment or a noise floor.

## Interpretation and limits

Serial wins every small-input cell on both hosts. At 4,194,304 values with four or eight workers, both parallel alternatives beat serial on every paired block by more than 5 percent. Their comparison remains unresolved in those large cells. A minimum median alone is not the winner rule.

Local/add versus rescan ties on Arm small/four and small/eight, and x86 small/four. Rescan beats local/add for Arm medium/one and x86 medium/four. All other local/add versus rescan cells are unresolved. On x86 medium/four, serial versus either parallel alternative is also unresolved; all other non-large-parallel cells favor serial.

Warm complete-operation measurements exclude input/output allocation, first-touch, validation and printing; include scratch allocation, dispatch, thread creation/join, summaries and data passes. Linux affinity is CPU0..7 inherited by children; individual worker placement and migration are uncontrolled within that set. Hosts are shared; load and frequency were not controlled. Serial first-touch, warm caches and one input family limit generalization.

Logical traffic and the work-span derivation explain possible mechanisms. There are no PMU traffic measurements, DRAM-bandwidth calibration, scheduler attribution, persistent-pool comparison, or architecture-population claims. The x86 A/A contrast is 21.5 percent, a reason to retain variability and unresolved cells. No failed measurement process or outlier was discarded.

Both SSH campaigns completed on the first attempt. No required Linux run is missing. Local diagnostic results were collected before source commit and retained outside the published comparison; final claims use the committed Linux source.
