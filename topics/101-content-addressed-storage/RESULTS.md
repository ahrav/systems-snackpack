# Results

Tested source: `a62ddbfea2222dc31ab56b8b5a5b2dd9fa305103`.

Each host passed 171 independent boundary/restore/payload comparisons across 57 inputs,
plus collision, corruption, collection and type-separation checks. Rust unit and doc tests pass.

## Exact storage counts

| Workload | Whole payload / encoded | Fixed payload / encoded | CDC payload / encoded |
| --- | ---: | ---: | ---: |
| identical | 1,048,576 / 1,048,637 | 1,048,576 / 1,059,092 | 1,048,576 / 1,055,648 |
| insert | 2,097,153 / 2,097,275 | 2,084,865 / 2,105,911 | 1,078,933 / 1,091,547 |
| overwrite | 2,097,152 / 2,097,274 | 1,052,672 / 1,071,409 | 1,078,932 / 1,091,587 |
| unrelated | 2,097,152 / 2,097,274 | 2,097,152 / 2,118,184 | 2,097,152 / 2,112,157 |

Encoded bytes include typed chunks and distinct typed manifests. Dictionary/index memory,
root-name metadata, allocator overhead, packing and physical media overhead are excluded.
Identical manifests deduplicate too. Repeated references retain their order.

## Ingest timing

Milliseconds, median [minimum, maximum], six fresh workers per cell. Winner requires
at least 5% lower elapsed time than each alternative in every paired block.
Unresolved means that rule found no winner. It does not establish equivalence.

| Host/workload | Whole | Fixed | CDC | Winner |
| --- | ---: | ---: | ---: | --- |
| arm/identical | 10.488 [10.247, 11.178] | 12.299 [12.100, 15.062] | 16.230 [16.062, 16.863] | whole |
| arm/insert | 10.627 [10.402, 11.293] | 11.965 [11.819, 12.311] | 16.345 [16.220, 16.701] | whole |
| arm/overwrite | 10.695 [10.365, 11.125] | 12.436 [12.209, 13.361] | 16.594 [16.166, 17.169] | whole |
| arm/unrelated | 10.844 [10.560, 11.601] | 12.321 [12.115, 13.024] | 16.264 [15.984, 16.589] | whole |
| x86/identical | 8.357 [8.289, 8.765] | 9.655 [9.563, 9.761] | 12.538 [12.431, 12.726] | whole |
| x86/insert | 8.376 [8.273, 8.561] | 9.508 [9.428, 9.709] | 12.659 [12.508, 12.933] | whole |
| x86/overwrite | 8.545 [8.346, 8.680] | 9.790 [9.620, 9.946] | 12.614 [12.421, 12.895] | whole |
| x86/unrelated | 8.625 [8.489, 12.556] | 9.736 [9.420, 14.230] | 12.817 [12.502, 18.266] | whole |
| local/identical | 23.241 [20.961, 24.938] | 22.164 [21.996, 23.025] | 24.511 [23.888, 31.572] | unresolved |
| local/insert | 22.034 [21.617, 25.440] | 24.661 [21.950, 25.912] | 26.658 [25.231, 28.706] | unresolved |
| local/overwrite | 27.406 [21.854, 37.353] | 26.463 [23.220, 31.596] | 28.373 [26.154, 34.898] | unresolved |
| local/unrelated | 29.746 [22.454, 40.230] | 26.007 [23.484, 29.687] | 31.195 [23.782, 34.568] | unresolved |

## Interpretation and scope

For these bytes, CDC retains the least encoded data after the one-byte insertion.
Fixed chunks retain the least encoded data after the aligned overwrite. Whole-file
storage retains the least encoded data for identical and unrelated versions. These
are exact workload-specific storage results. Timing winners appear separately above.

The 1 MiB synthetic data, balanced schedule, timing boundary, warmups and controls
are specified in README.md. Each Linux host ran 72 measured workers plus 12 warmups
on CPU 0. Rust 1.93.1 release mode; Python 3.9.25 on Linux. Host metadata and raw
samples are retained in evidence/. Local Python version is in local-bench.json.

This experiment measures a mixed Python/Rust in-memory ingest pipeline, including
subprocess launch and pipe costs. Production storage throughput, peak memory,
restore latency, compression, durability and concurrency remain unmeasured.

## Validation

All six repository gates pass: 548 unit/example tests and 159 doctests.
Writing and full-branch whitespace checks pass; logs are retained.
The source archive transfers have matching SHA-256 hashes. Only the temporary root
workspace member glob is narrowed for isolated Linux builds; implementation, checker,
driver, package manifest and toolchain bytes remain exact committed source.
