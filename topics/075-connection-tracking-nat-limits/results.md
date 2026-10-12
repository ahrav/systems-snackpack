# Exact committed-source results

Source commit: `68c02558acb595ec95034fcc1f6b661d7fa57392`. Inputs and archive identity are in
[EVIDENCE_RECEIPT.json](EVIDENCE_RECEIPT.json). Six fresh processes per candidate/cell;
times below are microseconds: median [minimum, maximum]. Selection requires
rival_ns/candidate_ns >= 1.05 in all six paired blocks against every rival.
Unresolved means no candidate met this rule, not proven equivalence.

## arm

Host `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`; kernel `6.12.110-135.202.amzn2023.aarch64`.
Compiler `rustc 1.98.1 (48a229cea 2026-09-01)`; opt-level3, target-cpu=native.
Pinned CPU0 from 64 allowed CPUs.

| Case | Boundary | Scan | Bitmap | Tree | Selection |
|---|---|---|---|---|---|
| tiny | full | 227.117 [225.420, 236.706] | 120.739 [119.386, 121.109] | 313.761 [312.061, 315.190] | bitmap |
| tiny | steady | 227.167 [225.046, 229.911] | 120.391 [117.165, 131.068] | 310.627 [308.936, 324.413] | bitmap |
| crowded | full | 10726.147 [10712.695, 10779.027] | 431.374 [426.415, 434.591] | 469.781 [468.874, 474.534] | bitmap |
| crowded | steady | 7739.569 [7733.874, 7753.057] | 343.846 [339.524, 345.707] | 329.627 [328.345, 334.123] | unresolved |
| full | full | 27505.468 [27469.994, 27593.258] | 837.172 [827.603, 838.584] | 504.960 [498.183, 511.977] | tree |
| full | steady | 24173.520 [24145.111, 24273.779] | 734.920 [732.647, 735.809] | 356.599 [351.966, 358.072] | tree |
| spread | full | 5646.675 [5595.417, 5693.292] | 376.756 [375.756, 386.764] | 1275.907 [1255.591, 1394.015] | bitmap |
| spread | steady | 2129.247 [2120.600, 2203.701] | 208.363 [206.079, 210.096] | 345.014 [339.517, 355.568] | bitmap |
| skew | full | 10053.345 [10037.240, 10073.736] | 421.111 [417.930, 424.739] | 1030.399 [985.810, 1067.327] | bitmap |
| skew | steady | 7108.256 [7038.729, 7138.579] | 330.575 [327.074, 332.460] | 303.377 [301.686, 309.677] | tree |
| short | full | 1.815 [1.758, 1.829] | 1.375 [1.283, 1.401] | 603.598 [588.205, 628.399] | bitmap |
| short | steady | 0.358 [0.345, 0.392] | 0.362 [0.352, 0.633] | 1.772 [1.553, 1.955] | unresolved |

## xxl

Host `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`; kernel `6.12.110-135.202.amzn2023.x86_64`.
Compiler `rustc 1.99.0 (b940084d7 2026-09-28)`; opt-level3, target-cpu=native.
Pinned CPU0 from 192 allowed CPUs.

| Case | Boundary | Scan | Bitmap | Tree | Selection |
|---|---|---|---|---|---|
| tiny | full | 255.284 [252.211, 339.050] | 102.788 [98.583, 162.397] | 262.522 [253.866, 393.585] | bitmap |
| tiny | steady | 348.071 [311.774, 376.843] | 191.654 [149.443, 205.456] | 475.039 [348.581, 477.253] | bitmap |
| crowded | full | 8827.971 [8821.603, 8926.716] | 383.331 [380.734, 389.559] | 364.851 [360.858, 380.159] | unresolved |
| crowded | steady | 6366.502 [6353.593, 6412.334] | 319.829 [318.793, 323.134] | 261.127 [256.811, 276.435] | tree |
| full | full | 22552.742 [22525.350, 23847.754] | 681.652 [673.999, 688.126] | 390.106 [385.190, 408.028] | tree |
| full | steady | 19831.544 [19804.480, 19994.097] | 604.505 [599.699, 613.045] | 284.173 [275.494, 293.455] | tree |
| spread | full | 4850.155 [4786.959, 4895.992] | 367.770 [357.257, 380.961] | 967.768 [939.706, 977.662] | bitmap |
| spread | steady | 1818.722 [1784.837, 1835.406] | 212.239 [207.639, 217.427] | 246.605 [231.241, 267.750] | bitmap |
| skew | full | 8277.056 [8264.719, 8347.696] | 380.533 [377.867, 387.692] | 847.890 [831.221, 857.482] | bitmap |
| skew | steady | 5809.766 [5798.782, 5926.669] | 311.924 [309.467, 326.102] | 226.537 [220.812, 251.796] | tree |
| short | full | 2.245 [2.172, 2.302] | 2.079 [1.942, 2.122] | 529.116 [526.920, 539.408] | unresolved |
| short | steady | 0.457 [0.432, 0.568] | 0.458 [0.424, 0.508] | 1.113 [1.072, 1.139] | unresolved |

## Interpretation and limits

Bitmap wins most construction-inclusive cells. Tree wins the full-pool trace and
hot-pool steady churn. Its empty free set makes exhausted-pool rejection cheap;
this is an implementation-based interpretation, not PMU attribution. Scan has
no selected cell. Short/full Arm selects
bitmap here although it was unresolved initially. Both campaigns are retained;
no additional run was made to seek a winner. Sub-microsecond short/steady cells
remain unresolved on both hosts.

Exact generated library assembly includes Arm rbit/clz and x86 tzcnt/blsr for
bit operations. No whole-process hardware-counter mechanism claim is made.
The hosts and compiler/LLVM versions differ. No ISA-family, Linux-NAT, packet
throughput, production randomization, timeout-engine or cloud-capacity win follows.
