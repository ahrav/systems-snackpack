# Committed-source local results

Source `bd99e4bdb3dce73eaa5f33973ec93acd6e0f3c97`. 108 independent processes passed all oracles.
Values are microseconds per response: median [minimum, maximum] of six process
averages. See measurements.md for the paired all-six-block 5% selection rule.

| Workload | 1 KiB cap | 4 KiB cap | 16 KiB cap | Winner |
|---|---:|---:|---:|---|
| 128 B, one write | 0.738 [0.726, 0.750] | 0.724 [0.718, 0.757] | 0.737 [0.731, 0.751] | Unresolved |
| 1 KiB, one write | 1.044 [1.000, 1.110] | 1.030 [0.994, 1.076] | 1.027 [0.988, 1.036] | Unresolved |
| 16 KiB, one write | 15.559 [15.258, 16.141] | 8.404 [8.238, 8.762] | 6.539 [6.172, 7.328] | 16 KiB |
| 1 MiB, one write | 1031.750 [1006.875, 1081.375] | 578.750 [562.250, 598.375] | 460.188 [443.875, 473.250] | 16 KiB |
| 16 KiB in 128 B writes | 94.502 [91.840, 101.547] | 94.221 [91.094, 99.773] | 94.223 [91.500, 96.441] | Unresolved |
| 1 MiB in 4 KiB writes | 1021.875 [998.375, 1055.875] | 550.625 [541.375, 603.375] | 555.813 [551.125, 564.250] | Unresolved |

The 16384 cap wins the two ready bulk cells among tested caps. Four cells remain
unresolved. At 4 KiB writes, 4096 and 16384 both generate 256 records; the
1024 cap generates 1024. At 128-byte writes, every cap generates 128 records.
Those record counts are observed. A causal decomposition of cryptography, calls,
allocation and copies is not measured.

Fixture setup (key/certificate/handshake) across all processes: median
846.500 us, range [761.000,1884.000]. Teardown:
median 36.500 us, range [16.000,259.000].
These are diagnostic observations outside selection timing, with no network.
Caller allocation, process startup, and cold-cache behavior are unmeasured.

Apple M1 Pro, Darwin 25.6.0,10 CPUs, uncontrolled scheduling, OpenSSL 3.6.2.
Compiler: Apple clang version 17.0.0 (clang-1700.4.4.1). Exact command/version/binary identity
is in EVIDENCE_RECEIPT.json and retained metadata. No explicit CPU/features flags;
OpenSSL dispatch is not separately identified. Initial results are retained
separately, not pooled. Required Linux runs failed Midway authentication before
identity/transfer, including exact-source follow-up attempts. Both remain pending.

Validation: all seven workspace gates pass; four Rust tests, one doctest,
102 C boundary-oracle cases and seven invalid-input rejections pass. The optional combined AddressSanitizer/UndefinedBehaviorSanitizer run did not
finish within a bounded two-minute observation and was terminated. It is
unverified and excluded from timings; the unsanitized boundary checks passed.
