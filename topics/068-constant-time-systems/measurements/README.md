# Exact committed-source results

Source `9f9c86feb00a8bdc74ad8e053875558522b591d5`; archive SHA256 `8dd3b786ab8e38da40719a57780d5644cffdea87259068093e596dda93639808`. Source/runner/lock hashes match both hosts. Raw process data, binaries, assembly and replay are retained outside Git at `/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-068/2026-10-05-9f9c86fe`.

Both hosts passed 3 unit tests, 1 doctest and 432 process checksums. Seven local workspace gates passed. See [frozen timing contract](../EXPERIMENT.md). This is throughput and code inspection, not a security certification or dudect campaign.

The receipt's `target_cfg` is `rustc --print cfg -C target-cpu=native` output: it lists the native target features and rustc's profile-free defaults, including `debug_assertions`. The measured binary came from `cargo build --release`, whose profile disables debug assertions; `build.log` on the evidence host records that build. Review commits after `9f9c86fe` change `scripts/run.py` (inherited `CARGO_ENCODED_RUSTFLAGS`/`CARGO_BUILD_TARGET` removal, toolchain capture from the build directory, pinned build CPU, `midr_el1` read from the pinned CPU with an existence guard, build timeout); the receipt pins the runner hash that produced these measurements, and `git show 9f9c86feb00a8bdc74ad8e053875558522b591d5:topics/068-constant-time-systems/scripts/run.py` reproduces that exact runner (SHA256 `7153b06e…`). A replay with the current runner on another aarch64 dev desk, with both inherited Cargo variables exported, rebuilt the arm `binary_sha256` `300689d8…` byte for byte, so the committed arm image is the native-flag build the receipt describes.

## arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com

Architecture `aarch64`; kernel `6.12.110-135.202.amzn2023.aarch64`; CPU `0x00000000411fd401`; 64 available logical CPUs; pinned CPU 0. rustc 1.98.1 (48a229cea 2026-09-01). Native release, LTO off, subtle default features disabled. Effective Cargo release debug assertions disabled. Toolchain/features in receipt. No architecture-only comparison.

Median [min,max] ns/call over 12 processes per candidate/cell.

| Bytes | Case | Early exit | XOR | subtle | Full-scan selection | subtle/XOR interval |
|---:|---|---:|---:|---:|---|---|
| 16 | first | 2.455 [2.372,2.785] | 3.487 [3.456,3.761] | 34.508 [33.679,35.782] | xor | 9.184–10.054 |
| 16 | last | 12.278 [12.113,12.861] | 3.489 [3.457,3.744] | 26.624 [25.010,35.588] | xor | 7.212–9.853 |
| 16 | equal | 12.832 [12.776,13.416] | 3.475 [3.456,3.753] | 25.542 [25.072,34.737] | xor | 7.174–9.726 |
| 32 | first | 2.459 [2.367,4.278] | 4.027 [4.010,4.306] | 41.740 [41.338,42.275] | xor | 9.922–10.459 |
| 32 | last | 23.387 [23.028,24.396] | 4.050 [4.009,4.317] | 41.429 [41.038,42.243] | xor | 9.736–10.353 |
| 32 | equal | 25.042 [24.771,25.639] | 4.025 [4.008,4.273] | 41.822 [41.240,42.209] | xor | 10.191–10.503 |
| 256 | first | 2.412 [2.345,2.761] | 8.042 [7.666,8.486] | 264.647 [263.894,266.627] | xor | 31.755–33.643 |
| 256 | last | 188.354 [183.250,192.780] | 8.043 [7.829,8.274] | 264.668 [263.701,266.401] | xor | 32.147–33.186 |
| 256 | equal | 192.464 [191.364,194.170] | 8.110 [7.692,10.612] | 264.434 [263.975,266.975] | xor | 31.572–33.095 |
| 4096 | first | 2.492 [2.382,2.764] | 83.748 [83.286,84.996] | 4055.333 [4045.922,4118.630] | xor | 48.352–48.898 |
| 4096 | last | 3094.500 [3068.333,3119.382] | 83.884 [83.529,84.591] | 4070.017 [4043.727,4138.673] | xor | 48.076–48.968 |
| 4096 | equal | 2973.384 [2937.362,3006.174] | 83.730 [83.376,84.963] | 4053.945 [4049.318,4093.973] | xor | 47.817–48.978 |

## xxl: dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com

Architecture `x86_64`; kernel `6.12.110-135.202.amzn2023.x86_64`; CPU `Intel Xeon Platinum 8488C`; 192 available logical CPUs; pinned CPU 0. rustc 1.98.0 (88d9e12ae 2026-08-18). Native release, LTO off, subtle default features disabled. Effective Cargo release debug assertions disabled. Toolchain/features in receipt. No architecture-only comparison.

Median [min,max] ns/call over 12 processes per candidate/cell.

| Bytes | Case | Early exit | XOR | subtle | Full-scan selection | subtle/XOR interval |
|---:|---|---:|---:|---:|---|---|
| 16 | first | 1.943 [1.941,2.035] | 3.908 [3.762,4.134] | 25.135 [25.022,26.022] | xor | 6.221–6.705 |
| 16 | last | 9.722 [9.699,10.818] | 3.854 [3.758,4.289] | 25.102 [25.041,26.654] | xor | 6.228–6.950 |
| 16 | equal | 8.975 [8.788,9.334] | 3.960 [3.756,4.153] | 25.104 [25.021,26.450] | xor | 6.231–6.742 |
| 32 | first | 1.942 [1.939,1.982] | 5.122 [4.858,5.273] | 45.295 [45.043,46.584] | xor | 8.739–9.280 |
| 32 | last | 16.151 [16.118,17.520] | 5.056 [4.849,5.571] | 45.203 [45.045,46.135] | xor | 8.416–9.323 |
| 32 | equal | 16.364 [16.273,17.030] | 4.976 [4.849,5.504] | 45.153 [45.103,45.637] | xor | 8.432–9.327 |
| 256 | first | 1.943 [1.941,1.991] | 5.657 [5.290,24.816] | 332.584 [331.124,347.915] | xor | 55.312–62.596 |
| 256 | last | 134.597 [133.550,137.293] | 5.373 [5.206,5.786] | 333.516 [331.084,341.205] | xor | 58.970–63.415 |
| 256 | equal | 137.274 [135.513,143.222] | 5.370 [5.143,5.924] | 332.180 [331.124,352.237] | xor | 58.499–64.548 |
| 4096 | first | 1.946 [1.939,15.153] | 47.953 [47.527,48.856] | 5164.395 [5147.745,5296.604] | xor | 105.951–109.610 |
| 4096 | last | 1942.149 [1938.009,1986.241] | 48.092 [47.712,49.595] | 5165.903 [5155.475,5203.209] | xor | 106.203–108.534 |
| 4096 | equal | 1942.108 [1937.921,2036.574] | 47.829 [47.448,49.136] | 5167.832 [5146.147,5294.867] | xor | 106.236–110.784 |

## Interpretation

XOR is the fastest correct full-scan candidate in all 12 cells on both hosts under the predeclared rule. Early exit has the lowest equality-only median for first mismatches; XOR has the lowest for last/equal. Early exit is rejected for secret comparison independently of timing rank. XOR is teaching code without a compiler security guarantee; subtle remains the library-backed option, not a benchmark-certified primitive.

The initial and final campaigns agree on those selections. Intervals are 2nd/11th ordered paired ratios (99.365% marginal iid sign coverage); no multiplicity adjustment or equivalence claim. Minimum useful difference is 2%. No measurement rerun was selected to manufacture a winner.

Observed linked XOR code uses Arm SVE/NEON reductions and x86 vector loads/ternary Boolean operations. Early has byte-dependent conditional branches. The subtle wrapper loops through per-byte comparisons with library-barrier calls. This is exact-image code-shape evidence; it does not prove all instruction latencies secret-independent or certify speculative/physical channels.

Warm resident buffers only; small and adversarial first/last mismatch cases included. No cold-cache, hidden-length, randomized leakage-class, network, protocol or attack-feasibility result. Shared host load/frequency and compiler-version differences limit generalization.
