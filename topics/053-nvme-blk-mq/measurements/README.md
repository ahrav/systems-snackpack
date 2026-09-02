# Measurement records

This directory holds compact records from exact-source runs on the required Arm
and x86-64 Linux hosts.

Each accepted host record must bind:

- the pushed source commit and path-limited archive SHA-256;
- target label, runtime-resolved hostname, architecture, kernel, processor,
  compiler, build flags, source digest, and binary digest;
- filesystem, mount, complete block stack, provider model, NVMe transport,
  interrupt inventory, and exported blk-mq topology;
- every fresh process result, balanced block order, per-process Linux storage
  counter deltas, integrity checks, and direct-I/O accounting;
- the depth-one versus depth-eight estimate and a whole-block interval;
- an A/A estimate and interval that can reject a noisy retained campaign;
- generated assembly for the timed userspace loop;
- a sealed external receipt archive, its SHA-256 and manifest digest, plus the
  independent validator result.

Full receipts remain outside Git. A compact comparison must distinguish direct
observations, calculated results, and inferences. It must state that application
depth does not prove queue occupancy, Linux AIO completion is not an NVMe
completion entry, device counters can contain ambient traffic, and a guest
Amazon Elastic Block Store device is not evidence for local flash.

Preliminary exploration is not publication evidence. Only receipts built from
the final path-limited Git archive qualify.
