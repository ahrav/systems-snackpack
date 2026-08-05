# Exact-source cross-host comparison

Both required hosts passed the same fixed User Datagram Protocol (UDP)
experiment at source commit
`750e9ea8729063d118409f9f73537d76cb8ad392`. On this loopback workload,
`sendmmsg` reduced elapsed time by a similar proportion on the two hosts.
`UDP_SEGMENT` had a larger observed reduction on the runtime-resolved `xxl`
host. The experiment does not identify architecture, processor, or kernel
mechanism as the cause of that difference.

## Paired elapsed estimates

Lower ratios are better. Each primary estimate uses eight complete
four-process blocks, or 32 fresh processes. Brackets are descriptive 95%
Student-t intervals over block log contrasts for one run window.

| Candidate / scalar | Arm host | `xxl` x86 host |
|---|---:|---:|
| `sendmmsg` | 0.92617 [0.91796, 0.93445] | 0.93385 [0.92971, 0.93800] |
| `UDP_SEGMENT` | 0.95531 [0.93810, 0.97283] | 0.78461 [0.77940, 0.78985] |
| A/A right / left | 0.99402 [0.96581, 1.02305] | 0.99251 [0.98023, 1.00494] |

| Descriptive median nanoseconds/logical datagram | Arm host | `xxl` x86 host |
|---|---:|---:|
| scalar | 2,902.70 | 2,612.85 |
| `sendmmsg` | 2,686.03 | 2,439.47 |
| `UDP_SEGMENT` | 2,768.51 | 2,044.16 |

Absolute medians are host observations, not a controlled host-to-host speed
comparison. The paired ratios are the primary estimands.

## What the records establish

- All 82 fixed attempts passed on each host. No failed process was replaced.
- Sender central processing unit (CPU) 0 and receiver CPU 1 remained fixed, singleton-affined, and
  directly observed in every process.
- Scalar made 32,000 measured send calls per process. The normal successful
  batched paths made 1,000, one per measured round.
- The separate UDP Generic Receive Offload (`UDP_GRO`) control preserved 128
  logical datagrams and their checksum, with four 32-segment aggregate control
  messages on each host.
- The Arm and x86-64 linked images retained the intended scalar `send`,
  partial-aware `sendmmsg`, and one-`sendmsg` `UDP_SEGMENT` paths.
- The source archive, source tree, experiment-file hashes, final binary,
  before/after repository manifests, gate logs, raw process rows, and evidence
  manifest all passed independent validation.

## What remains inferred or untested

The lower elapsed ratios are measured. Reduced fixed system-call and software
submission cost is a mechanism consistent with the call counts and cost model,
but the experiment did not trace kernel functions. The larger `UDP_SEGMENT`
effect on `xxl` could reflect processor, cache, scheduler, kernel timing, or
other host-specific conditions. The two hosts do not isolate those causes.

Loopback bypassed the Elastic Network Adapter (ENA), physical receive and transmit
queues, direct memory access, hardware Receive-Side Scaling, interrupts, and
the wire. The default-interface driver, queue, and steering observations are
context only. No result generalizes to Arm, x86-64, ENA, a cloud instance
family, a physical network, or another payload and batch shape.

See the [Arm record](750e9ea-arm.md), [`xxl` record](750e9ea-xxl.md), and
[sealed raw bundles](raw/750e9ea).
