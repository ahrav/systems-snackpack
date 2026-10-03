# Exact committed-source local results

Source commit `a6abe84804454a28a4cf93f999e608383b1880f6`. See [receipt](receipt.json) for hashes and host/build details.

Apple M1 Pro, arm64 Darwin25.6.0, rustc1.93.1/LLVM21.1.8, `-O -C target-cpu=native`, 10 logical CPUs, no CPU affinity. Six independent balanced processes per candidate/case; 486 total. Every checksum, 8 unit tests and 1 doctest passed. All seven required workspace gates passed.

Each cell is median [min,max] microseconds/query across process estimates. Life1/life16 include allocation, conversion, reads and drop, divided by query count. Source creation, oracle, visit lists and process startup are excluded. Selection requires >=5% paired advantage in every block over every alternative; unresolved means insufficient separation by that descriptive rule, not statistical equivalence.

| Rows | Operation | Boundary | AoS us | SoA us | AoSoA16 us | Selection (lowest median if unresolved) |
|---:|---|---|---:|---:|---:|---|
| 31 | narrow | resident | 0.007 [0.007,0.007] | 0.007 [0.007,0.007] | 0.009 [0.009,0.009] | unresolved (soa) |
| 31 | narrow | life1 | 0.011 [0.011,0.012] | 0.336 [0.332,0.449] | 0.118 [0.115,0.127] | aos |
| 31 | narrow | life16 | 0.007 [0.007,0.007] | 0.028 [0.027,0.029] | 0.015 [0.015,0.016] | aos |
| 31 | wide | resident | 0.016 [0.016,0.017] | 0.049 [0.047,0.051] | 0.079 [0.078,0.082] | aos |
| 31 | wide | life1 | 0.021 [0.020,0.026] | 0.402 [0.389,0.420] | 0.229 [0.223,0.255] | aos |
| 31 | wide | life16 | 0.017 [0.017,0.018] | 0.072 [0.070,0.080] | 0.090 [0.088,0.092] | aos |
| 31 | indexed | resident | 0.025 [0.024,0.027] | 0.054 [0.054,0.055] | 0.052 [0.051,0.053] | aos |
| 31 | indexed | life1 | 0.029 [0.028,0.030] | 0.388 [0.381,0.396] | 0.161 [0.159,0.167] | aos |
| 31 | indexed | life16 | 0.026 [0.025,0.027] | 0.076 [0.073,0.079] | 0.060 [0.056,0.061] | aos |
| 4096 | narrow | resident | 2.550 [2.410,2.654] | 0.330 [0.313,0.347] | 1.962 [1.901,2.053] | soa |
| 4096 | narrow | life1 | 2.510 [2.371,2.574] | 24.103 [22.025,25.984] | 15.326 [14.113,15.557] | aos |
| 4096 | narrow | life16 | 2.508 [2.482,2.624] | 1.764 [1.756,1.827] | 2.801 [2.757,2.898] | soa |
| 4096 | wide | resident | 3.184 [3.121,3.271] | 3.540 [3.442,3.600] | 15.799 [15.549,16.171] | aos |
| 4096 | wide | life1 | 3.243 [3.242,3.388] | 27.174 [26.408,28.284] | 29.717 [29.350,31.074] | aos |
| 4096 | wide | life16 | 3.160 [3.145,3.382] | 5.165 [4.899,5.333] | 16.744 [16.243,17.340] | aos |
| 4096 | indexed | resident | 4.856 [4.847,4.893] | 13.177 [13.003,13.547] | 15.004 [14.941,15.460] | aos |
| 4096 | indexed | life1 | 5.180 [4.901,5.361] | 37.204 [35.674,39.426] | 28.523 [27.690,29.471] | aos |
| 4096 | indexed | life16 | 5.068 [4.846,5.286] | 15.287 [14.868,15.529] | 16.110 [15.603,16.636] | aos |
| 1048576 | narrow | resident | 1135.154 [1132.724,1155.880] | 138.293 [126.799,141.177] | 492.533 [491.130,504.010] | soa |
| 1048576 | narrow | life1 | 1136.167 [1123.584,1160.875] | 7551.917 [7370.083,10574.458] | 3794.354 [3759.667,3822.916] | aos |
| 1048576 | narrow | life16 | 1164.845 [1123.354,1392.427] | 606.861 [586.034,848.896] | 759.171 [699.492,949.047] | soa |
| 1048576 | wide | resident | 1219.715 [1123.310,1343.135] | 1134.359 [1112.438,1257.169] | 4025.546 [3938.325,4225.477] | unresolved (soa) |
| 1048576 | wide | life1 | 1124.354 [1116.250,1137.750] | 7426.438 [7336.458,8520.750] | 7144.666 [7084.833,7287.833] | aos |
| 1048576 | wide | life16 | 1138.772 [1128.825,1176.247] | 1545.382 [1518.169,1713.536] | 4135.802 [4127.950,4401.099] | aos |
| 1048576 | indexed | resident | 10799.042 [10099.755,10955.422] | 27988.266 [26385.211,29440.839] | 30121.214 [29919.430,32953.659] | aos |
| 1048576 | indexed | life1 | 11066.292 [10447.375,11819.708] | 38051.958 [35853.667,38444.583] | 36960.709 [34198.375,39114.583] | aos |
| 1048576 | indexed | life16 | 11060.333 [10921.969,11440.216] | 29429.500 [28969.391,30312.419] | 32851.341 [30380.487,33607.456] | aos |

## Selection and limits

SoA wins narrow resident scans at4096 and1048576 rows and their16-query lifecycles. AoS wins all one-query lifecycles, all indexed whole-row cases, and the other resolved cases. The31-row resident narrow scan and1048576-row resident all-field scan remain unresolved. AoSoA16 wins no declared workload. This ranks these implementations, including their natural traversal, not every possible tiled implementation.

The exact linked local binary has scalar unrolled loads at64-byte strides in row_narrow and NEON vector loads/additions in Columns::narrow. This confirms different code shapes; no counters isolate their causal share of the timing difference. No architecture-family conclusion, best tile width, update throughput, NUMA or cold-cache claim.

Raw evidence is outside Git at `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-066/2026-10-03-a6abe848`. The first committed-source run overlapped workspace builds; its timings are excluded. A single unchanged replacement ran after the gates completed. Initial scratch results and every attempt are retained.

## Required Linux follow-up

Arm host dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com and runtime-resolved xxl (dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com) both rejected SSH twice with expired Midway authentication. No Linux source transfer, host-architecture check or execution succeeded.

After authentication is restored: re-resolve xxl, verify Arm aarch64 and xxl x86_64, transfer only the frozen replay files with matching SHA256 values from receipt.json, run `python3 scripts/run.py <new-output-dir>`, verify source and runner hashes, retrieve evidence and record each actual host. These are pending measurements; macOS does not satisfy them.

## Catalog note

Current origin/main curriculum.toml contains sessions1..12 and no Topic066 catalog entry. The user-provided topic rotation supplies the identity Data layout transformations; the scoped session66 entry is retained in rounds/catalog-entry.toml. The guarded publisher does not permit root-catalog changes. No earlier topic directories were changed.
