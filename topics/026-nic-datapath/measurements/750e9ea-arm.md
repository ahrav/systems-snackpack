# Exact-source Arm loopback record

The checked-in User Datagram Protocol (UDP) experiment passed correctness, source, code-generation,
workspace, and receipt gates on the required Arm host. For this binary and run
window, `sendmmsg` used 0.9262 times scalar elapsed time and `UDP_SEGMENT` used
0.9553 times scalar elapsed time. This is a Linux loopback result, not a
physical network interface controller (NIC) result.

## Identity and host

| Field | Retained value |
|---|---|
| Run window | 2026-08-05 15:26:16Z to 15:26:37Z |
| Requested and resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` |
| Source commit and tree | `750e9ea8729063d118409f9f73537d76cb8ad392`, `74926ef177f0fd9329e13a35e38069dc38fb152a` |
| Source archive SHA-256 (Secure Hash Algorithm 256-bit digest) | `76507ad35016e704c81c4e1d125a321de14305b1821da8cb05705c3e47f6e210` |
| Final binary SHA-256 | `fc7710757226fff992307d7bfaeaac336fadaedd85991b78bcf4e58101532c64` |
| Architecture and kernel | `aarch64`, `6.12.94-123.192.amzn2023.aarch64` |
| Central processing unit (CPU) evidence | Arm implementer `0x41`, part `0xd40`; 64 online CPUs, one socket, 64 cores, one thread per core |
| Selected CPUs | sender 0, receiver 1, unchanged across all 82 processes; post-run topology query mapped them to cores 0 and 1 |
| C toolchain | GNU Compiler Collection (GCC) 11.5.0, target `aarch64-amazon-linux` |
| Rust toolchain | Rust 1.95.0, LLVM 22.1.2 compiler backend |
| C build flags | `-O3 -std=c11 -Wall -Wextra -Werror -Wpedantic -D_GNU_SOURCE -fno-lto -fno-omit-frame-pointer -pthread` |

The loopback maximum transmission unit (MTU) was 65,536 bytes. The unused
physical `eth0` interface reported Elastic Network Adapter (ENA) driver
2.17.2g, MTU 9,001, eight receive queues, and eight transmit queues. Receive
Packet Steering (RPS), Receive Flow Steering (RFS), and Transmit Packet
Steering (XPS) maps were zero. `ethtool` was unavailable. These are host
configuration observations; loopback did not traverse ENA, its queues, direct
memory access, or the wire.

Both socket buffer defaults and maxima were 212,992 bytes. The host reported
`netdev_max_backlog=1000`, `netdev_budget=300`,
`netdev_budget_usecs=20000`, `somaxconn=4096`, and
`tcp_max_syn_backlog=4096`. TCP receive autotuning was enabled. Busy-read and
busy-poll budgets were zero.

## Timed design and result

Each mode sent 32 UDP datagrams of 1,200 bytes per round. One fresh process ran
100 warmup rounds and 1,000 measured rounds. Eight complete, position-balanced
four-process blocks estimated each candidate/scalar ratio. Four separate A/A
same-treatment diagnostic blocks used the same `sendmmsg` command under both
labels. All payloads were
prebuilt in setup and first-touched on the pinned sender CPU. The measured
interval covered one contiguous send, receive, verification, and
acknowledgement phase.

| Ratio | Point estimate | Descriptive 95% log-t interval | Blocks |
|---|---:|---:|---:|
| `sendmmsg` / scalar | 0.92617 | [0.91796, 0.93445] | 8 |
| `UDP_SEGMENT` / scalar | 0.95531 | [0.93810, 0.97283] | 8 |
| A/A right / left | 0.99402 | [0.96581, 1.02305] | 4 |

The interval uses dispersion among complete block contrasts in this run
window. Repeated-block independence and normality are assumptions, not
properties established by fresh processes.

Descriptive median elapsed times were 2,902.70 ns per logical datagram for
scalar, 2,686.03 ns for `sendmmsg`, and 2,768.51 ns for `UDP_SEGMENT`.
Program-reported setup medians were 18.88 to 18.95 ms across primary modes and
were excluded from the paired elapsed estimator. The outer process envelope
also remained outside the estimator.

The median send-call counts were 32,000 for scalar and 1,000 for each batched
mode. Median receive-call counts were 16,741 for scalar, 8,211 for
`sendmmsg`, and 1,000 for `UDP_SEGMENT`. These program counters are harness
correctness receipts, not an independent system-call trace.

## Semantic and code-generation checks

The separate four-round UDP Generic Receive Offload (`UDP_GRO`) control
verified the same 128 logical datagrams and checksum with and without UDP GRO.
The enabled path returned four control messages and at most 32 logical
segments per receive. No timing claim uses this control.

Linked-image inspection found Procedure Linkage Table (PLT) call stubs:
`send@plt` inside the scalar loop, `sendmmsg@plt` inside a partial-completion retry loop, and
`sendmsg@plt` in the `UDP_SEGMENT` path. This proves final-binary call shape. It
does not prove a kernel branch or device action.

The [sealed raw bundle](raw/750e9ea/arm) contains all 82 process attempts,
complete-block analysis, source and binary identities, host metadata, full
disassembly, workspace-gate logs, before/after source manifests, and its
evidence hash manifest. The independent validator passed before and after the
bundle was sealed.
The hashed [topology supplement](raw/750e9ea/topology-supplement.txt) is a
post-run read-only query, not part of the sealed bundle.
