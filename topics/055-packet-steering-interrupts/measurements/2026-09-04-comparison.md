# Exact-source packet-steering comparison

Both required hosts built the same path-limited Topic 55 archive and passed
the same 24-period bidirectional campaign. The fixed order was four treatment
blocks, `ABBA BAAB ABBA BAAB`, followed by two identical-operation controls,
`XYYX YXXY`. Every period used fresh client and server processes. No elapsed
value contributes to the result.

## Host and source identity

| Property | Arm | `xxl` |
|---|---|---|
| runtime host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| architecture | AArch64 | x86-64 |
| CPUs | 64 | 192 |
| kernel | `6.12.100-125.179.amzn2023.aarch64` | `6.12.95-124.187.amzn2023.x86_64` |
| driver | ENA 2.17.2g | ENA 2.17.2g |
| RX / TX queues | 8 / 8 | 16 / 16 |
| binary SHA-256 | `f7cba2f8a9d43ef93622eae2c3be5d0ad347b309e401ef684c96f74d717fea2a` | `5a55668b537eb48a1431198bafc3336a8414d42dff446f2bc1732cef411b844d` |

The common source commit was
`d20ee11bbb3c2cef2e98a69194d287783c5e29d6`. The common archive SHA-256 was
`ceb897467ae5842961acd99bf682f5d5d50346874c09117ebfec890baba8f95e`.
The common probe source SHA-256 was
`554a5f7b974c85e8c93311a49b90a9668ab264a6ca5d38df0d8b219111ae50ef`.

## Accepted observations

| Observation | Arm | `xxl` |
|---|---:|---:|
| fresh client outputs | 24 | 24 |
| fresh server outputs | 24 | 24 |
| one-flow client runs | 8 | 8 |
| 128-flow client runs | 16 | 16 |
| observations per output | 256 | 256 |
| stable, known client CPU flows | all | all |
| stable, positive client NAPI flows | all | all |
| unique CPUs in every 128-flow run | 8 | 16 |
| unique NAPI IDs in every 128-flow run | 8 | 16 |
| observed RPS / RFS / XPS maps | zero | zero |
| route interface | `eth0` | `eth0` |
| independent validator | pass | pass |

Measured on these hosts: all request and echo identities were complete and
byte-correct; every 128-flow client run kept all sockets live and used distinct
source endpoints; each connected flow reported stable incoming CPU and NAPI
values. The one-flow case reported one CPU and one NAPI identifier per client
process. The many-flow case reported eight on Arm and 16 on `xxl`.

Sourced mechanism: Linux documents RSS as NIC receive-queue selection, RPS as
later software CPU selection, RFS as application-locality-aware RPS, and XPS
as transmit-queue selection. The host files show that optional software maps
were disabled during this run.

Inferred: the positive NAPI fanout is consistent with hardware or
driver-managed receive fanout before RPS or RFS. The unavailable `ethtool`
interface prevents a direct claim about RSS keys, hash fields, or indirection
entries.

Not established: the experiment does not compare steering configurations,
measure performance, count packets through interrupts, or isolate an Arm,
x86-64, CPU-vendor, instance-type, or queue-count effect. The shared server
socket records peer identity and completeness, not per-flow CPU placement.

The compact source, validator outputs, alias resolution, and external receipt
locators are in [`raw/2026-09-04-d20ee11`](raw/2026-09-04-d20ee11/README.md).
