# Exact-source depth comparison

Both required hosts built from the same path-limited source archive and passed the
same 64-process design, workload-integrity checks, and independent sealed
receipt validation. Only these two accepted sealed receipts contribute the
reported timings.

## Host and path identity

| Property | Arm | `xxl` |
|---|---|---|
| runtime host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| architecture | AArch64 | x86-64 |
| instance / CPU | `c7g.16xlarge`, ARM model 1 | `c7i.48xlarge`, Intel Xeon Platinum 8488C under KVM |
| kernel | `6.12.100-125.179.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| filesystem | XFS on `/dev/nvme0n1p1` | XFS on `/dev/nvme0n1p1` |
| guest parent | 11.7 TiB Amazon EBS `nvme0n1` | 2 TiB Amazon EBS `nvme0n1` |
| scheduler / hardware contexts | `none` / 2 | `none` / 2 |
| tags per context / `nr_requests` | 63 / 63 | 255 / 255 |
| binary SHA-256 | `6096b67585760969cd66fe94ad8fee336e43e1946cc6ff557e321a37fab5a7d2` | `099d7f9250bb3586c2766984743bb5ee75a2f16b39b523687f75247e0de51bb3` |

The source commit was
`82c98a25eb4ad31fd9e18fc8d8f9463dab6854d7`; the common archive SHA-256 was
`44085d1001f8566bdf0f7a58af509b8b7acb1f633c09f1f7c218a88ab85e4c45`.
Native binaries differ because each host compiled with `-march=native` for its
own architecture.

## Accepted measurements

Each process performed 8,192 verified 4 KiB `O_DIRECT` reads, exactly
33,554,432 bytes. Each host ran 32 depth-comparison processes and 32 A/A
processes. There were eight fixed, balanced four-process blocks per scenario;
a complete block was the analysis unit.

| Result | Arm | `xxl` |
|---|---:|---:|
| q1 IOPS min / median / max | 1,739.997 / 1,748.534 / 1,750.474 | 1,741.235 / 1,749.317 / 1,759.325 |
| q8 IOPS min / median / max | 13,952.510 / 13,974.410 / 14,001.019 | 8,654.344 / 13,916.278 / 14,044.350 |
| q8/q1 point ratio | 7.996451 | 6.955513 |
| q8/q1 95% whole-block t interval | [7.988423, 8.004487] | [6.312387, 7.664163] |
| A/A Y/X point ratio | 0.999347 | 0.998959 |
| A/A 95% whole-block t interval | [0.998555, 1.000139] | [0.996977, 1.000945] |
| A/A point in [0.95, 1.05] | pass | pass |
| A/A interval contains 1 | pass | pass |
| A/A interval within [0.90, 1.10] | pass | pass |
| valid attempts / unique PIDs | 64 / 64 | 64 / 64 |

The Arm depth ratios were tightly grouped near eight. The `xxl` depth ratios
ranged from 6.297372 to 8.014782, producing the wider accepted interval. No
block was removed. The cause of that variation was not isolated.

## What the receipts establish

Measured on each exact host: changing only the probe's maximum outstanding
Linux AIO reads from one to eight increased application IOPS. All timed
processes remained single-threaded, reported zero errors, verified every read,
accounted exactly 33,554,432 process read bytes, and reached the requested
application outstanding limit. Both independent validators returned
`pass: true`, `sealed: true`, and `measurement_usable: true`.

Calculated: the q8/q1 estimates and intervals are geometric whole-block log
contrasts across eight blocks, with two-sided Student-t limits and 7 degrees of
freedom. They describe between-block variation inside one host-specific run
window. The 8,192 inner reads are workload, not independent samples.

Inferred: both results are consistent with depth one leaving less overlapped
work available to the complete observed path than depth eight. They are not a
measurement of any one internal queue or service stage.

## What the receipts do not establish

- Application `peak_outstanding=8` does not prove eight requests occupied one
  blk-mq hardware context or one NVMe submission queue. The hardware-context
  and tag inventories are static topology observations, not occupancy traces.
- A Linux AIO completion returned by `io_getevents` is not an NVMe
  completion-queue entry. The experiment did not trace blk-mq requests, driver
  commands, submission-queue doorbells, completion interrupts, or NVMe command
  identifiers.
- Per-process device counter windows are system-wide and may include ambient
  traffic. Adjacent `nvme0n1p1` and `nvme0n1` counters are not additive.
- The guest devices identify themselves as Amazon Elastic Block Store and use
  the NVMe interface. That does not establish local PCIe flash or isolate
  controller, cache, network, service, or physical-media latency.
- The two hosts differ in architecture, CPU vendor and topology, kernel,
  instance type, volume identity and size, tag inventory, and run window.
  Their difference does not establish an Arm, x86-64, Intel, NVMe, EBS, XFS,
  or vendor-wide causal effect.

Retained assembly binds the workload to calls into the C library's `syscall`
wrapper for `io_submit` and `io_getevents`: AArch64 uses `bl
<syscall@plt>` and x86-64 uses `call <syscall@plt>`. Userspace disassembly does
not reveal blk-mq dispatch or a device completion.

The compact source, controller-validation, alias-resolution, and external
receipt locators are in [`raw/2026-09-01-82c98a2`](raw/2026-09-01-82c98a2/README.md).
