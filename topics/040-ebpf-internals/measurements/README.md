# Topic 40 measurement contract

This topic retains correctness and generated-code evidence, not a performance
ranking. The C probe asks Linux to load three tiny socket-filter programs. It
checks the permission boundary, verifier rejection, translated and just-in-time
(JIT) compiled bytes, attachment, and accept/drop behavior on loopback User
Datagram Protocol (UDP) sockets.

Each required host runs the same Git-created source archive. One independently
launched privileged process is one correctness replicate. Eight fresh processes
must pass without retry. The retained evidence includes every process stream,
the submitted and returned instruction bytes, verifier logs, generated blobs,
native disassembly, source and executable hashes, host and toolchain identity,
selected kernel configuration, sysctls, and a manifest of receipt digests.

The 250-millisecond receive timeout distinguishes a drop from a received packet.
It is not a latency measurement. No elapsed-time, throughput, instruction-set,
or processor-vendor comparison is justified.

[`../rounds/01.md`](../rounds/01.md) defines the acceptance contract. The first
retained run passed on both required hosts:

- [`2026-08-19-arm.md`](2026-08-19-arm.md)
- [`2026-08-19-xxl.md`](2026-08-19-xxl.md)
- [`2026-08-19-comparison.md`](2026-08-19-comparison.md)

The sealed raw archives and source identity are under
[`raw/2026-08-19-f32d0db/`](raw/2026-08-19-f32d0db/).
