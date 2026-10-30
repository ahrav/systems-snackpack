# Measurements

Measured source and runner: `c95f437f1e910b440e3f80a3fb92ca5768ce16db`.
Archive SHA-256: `7ecbc10f091cf6405e3ffc2b96483129b7908d18d853d5c9e164a640fec9274b`.
Both remote archive hashes matched before testing. Published source/runner parity is checked separately.
Rust 1.93.1, Cargo release profile, default target CPU, no custom RUSTFLAGS.

Each host passed 3 unit tests and 1 doctest, plus 37,750 decoder comparisons across 18,875 inputs.
The independent Python parser accepted 3,834 inputs. Full IDs and payload bytes match both Rust paths.
Corpus SHA-256: `e2c44f4f73ea38ab15564a2e2ae29b1c4baad2d7a8f13d93a6c57cc5ebfa90ec`.

Each host ran 96 measured fresh processes plus 12 excluded warmups.
Eight paired blocks alternate borrowed/owned and owned/borrowed order for each workload.
Values below are microseconds per decoded-and-consumed batch: median [minimum, maximum].
A winner requires all eight pairs to exceed 5% in that direction. All eight pairs within 5% form a tie.
Remaining cases are unresolved. These are descriptive comparisons without a population confidence interval.

## Linux AArch64: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com

| Workload | Borrowed, us | Owned, us | Result |
|---|---:|---:|---|
| small_sparse | 0.203 [0.202, 0.209] | 4.970 [4.943, 4.984] | borrowed |
| small_full | 0.913 [0.911, 0.950] | 5.449 [5.427, 5.483] | borrowed |
| large_sparse | 3.040 [3.029, 3.083] | 135.559 [134.898, 136.089] | borrowed |
| large_full | 45.432 [45.292, 47.944] | 180.642 [177.844, 182.976] | borrowed |
| repeated_metadata | 515.415 [515.163, 517.488] | 151.658 [151.174, 154.959] | owned |
| repeated_payload | 30.241 [29.659, 30.895] | 29.900 [29.867, 30.314] | tie |

## Linux x86-64: xxl, Intel Xeon Platinum 8488C

| Workload | Borrowed, us | Owned, us | Result |
|---|---:|---:|---|
| small_sparse | 0.201 [0.201, 0.204] | 3.569 [3.556, 3.602] | borrowed |
| small_full | 0.789 [0.785, 0.813] | 4.016 [3.940, 4.047] | borrowed |
| large_sparse | 5.413 [5.379, 5.490] | 112.691 [110.771, 113.134] | borrowed |
| large_full | 83.327 [83.117, 85.828] | 189.447 [188.456, 193.597] | borrowed |
| repeated_metadata | 374.938 [374.753, 385.652] | 141.935 [140.982, 147.233] | owned |
| repeated_payload | 23.905 [23.792, 23.973] | 25.093 [25.020, 25.506] | unresolved |

## Local macOS arm64

| Workload | Borrowed, us | Owned, us | Result |
|---|---:|---:|---|
| small_sparse | 0.093 [0.093, 0.093] | 2.110 [2.053, 2.134] | borrowed |
| small_full | 0.388 [0.382, 0.400] | 2.276 [2.250, 2.553] | borrowed |
| large_sparse | 1.506 [1.467, 1.679] | 14.327 [14.243, 15.458] | borrowed |
| large_full | 26.631 [23.034, 29.398] | 42.564 [37.974, 44.187] | borrowed |
| repeated_metadata | 186.226 [177.331, 196.491] | 76.034 [74.614, 83.354] | owned |
| repeated_payload | 7.823 [7.769, 8.127] | 9.958 [9.901, 10.276] | borrowed |

## Interpretation and limits

Borrowed wins all four one-pass workloads on all three hosts. Owned wins repeated_metadata on all three.
Repeated payload scans tie on Arm, remain unresolved on x86, and favor borrowed locally.
Repeated_metadata has empty payloads: the owned path materializes native IDs and empty Vec descriptors,
then scans them 32 times. It has one outer allocation and no payload allocations for those empty vectors.
The timing supports that workload-specific choice. Attribution to individual instructions or cache effects
is inference; hardware counters and assembly were not analyzed.

Both implementations validate the whole message. The owned baseline copies every payload, even on sparse reads.
Selective copying and arena allocation are useful further alternatives; their performance is unmeasured here.
Sparse large reads consume 32,768 payload bytes; eager owned decode copies all 524,288 payload bytes first.
Both retain the original input throughout this benchmark. Production memory release benefits of owned
records therefore require separate retention and peak-memory measurements.

Input generation, process startup and I/O are excluded. Allocation, copy and drop are included for owned.
Buffers are reused and warm. Linux is pinned to CPU 0. Frequency, thermals, SMT and competing host load
are uncontrolled. Workload results apply to this custom format and implementation. Network, compression,
production serialization libraries, cold storage, allocator alternatives and retained byte-time are unmeasured.
Raw host metadata, all samples and correctness counts are in evidence/.

An initial local build ran from the parent directory and selected the host-default toolchain.
That entire campaign is retained only in the standalone outputs under local-excluded-toolchain.
It is excluded from these tables. The full final local campaign rebuilt with explicit Rust 1.93.1.
The first validation command also ran from the parent directory and found no Cargo.toml;
subsequent validation used the worktree root. These setup errors are separate from decoder correctness.

## Repository validation

All six repository gates passed: formatting, Clippy with warnings denied, 529 unit/example tests,
151 doctests, benchmark compilation and documentation with warnings denied. Writing-policy and
full-branch whitespace checks passed. Gate logs are retained in evidence/gates. Committed text logs
only normalize trailing blank lines; original tool output remains in the standalone evidence.
The Linux Arm CPU reports implementer 0x41, part 0xd40; exact kernel and CPU metadata are retained.
