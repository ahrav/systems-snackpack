# Exact committed-source measurements

Measured source: `a637af7f65a00d7da75040400a9545df66a3fc87`. Final publication may add documentation and receipts; source/runner identities remain those in receipt.json.

Median milliseconds [observed minimum, maximum], six independent processes per candidate/cell. Selection requires every paired rival/candidate ratio >= 1.05 against both rivals.

| Host / workload | Dense ms | Sparse ms | Prealloc ms | Selected |
|---|---:|---:|---:|---|
| arm / small_empty | 2.568 [2.448, 3.054] | 1.204 [1.116, 1.322] | 1.199 [1.161, 1.247] | unresolved |
| arm / small_scatter | 3.342 [3.229, 3.379] | 3.120 [3.014, 4.061] | 3.544 [2.985, 4.310] | unresolved |
| arm / small_dense | 4.833 [3.926, 5.099] | 4.066 [3.948, 4.267] | 4.512 [3.993, 5.083] | unresolved |
| arm / large_empty | 10.275 [9.796, 12.108] | 1.757 [1.679, 1.796] | 1.767 [1.566, 1.869] | unresolved |
| arm / large_scatter | 13.163 [13.001, 13.493] | 6.568 [6.435, 6.766] | 6.628 [6.423, 6.902] | unresolved |
| arm / large_cluster | 14.814 [14.632, 15.415] | 9.286 [9.108, 9.549] | 9.588 [9.199, 9.894] | unresolved |
| arm / large_dense | 37.468 [37.154, 37.912] | 42.291 [42.011, 44.137] | 42.127 [41.864, 42.485] | dense |
| arm / tail_scatter | 3.884 [3.386, 5.265] | 3.929 [3.036, 4.468] | 3.126 [2.942, 3.575] | unresolved |
| x86 / small_empty | 0.965 [0.880, 1.538] | 0.431 [0.391, 0.510] | 0.444 [0.414, 1.320] | unresolved |
| x86 / small_scatter | 1.252 [1.108, 2.169] | 1.158 [0.971, 1.204] | 1.063 [1.008, 1.469] | unresolved |
| x86 / small_dense | 1.613 [1.241, 2.162] | 1.525 [1.266, 2.280] | 1.509 [1.417, 1.898] | unresolved |
| x86 / large_empty | 9.184 [7.963, 11.054] | 1.027 [0.532, 1.188] | 1.153 [0.558, 1.546] | unresolved |
| x86 / large_scatter | 310.909 [257.211, 338.839] | 270.697 [239.906, 295.021] | 261.682 [211.599, 279.197] | unresolved |
| x86 / large_cluster | 11.462 [10.343, 253.736] | 7.462 [6.055, 229.567] | 6.382 [5.810, 277.520] | unresolved |
| x86 / large_dense | 36.766 [35.024, 41.011] | 37.478 [34.858, 39.770] | 37.728 [33.637, 40.015] | unresolved |
| x86 / tail_scatter | 1.550 [1.139, 2.388] | 1.145 [1.017, 1.888] | 1.031 [0.956, 1.594] | unresolved |

See [contract](contract.md) for exclusions and [receipt](receipt.json) for source and host identities. The full JSON preserves phase, cleanup, allocation and paired-ratio data.
