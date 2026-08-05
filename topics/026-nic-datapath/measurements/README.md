# Measurement contract

Each retained record applies only to its source identity, final binary, host,
kernel, compiler, loopback route, socket configuration, CPUs, datagram shape,
schedule, and run window. It is not physical-NIC performance evidence.

## Required record fields

- requested endpoint, SSH alias when used, resolved hostname, architecture,
  CPU model, kernel, available and allowed CPUs, selected CPUs, sibling maps,
  compiler, build flags, and run window;
- interface and driver identity, queue counts, feature visibility, interrupt
  affinity, receive-side scaling, Receive Packet Steering, Receive Flow
  Steering, Transmit Packet Steering, NAPI controls, socket limits, backlog
  controls, busy-poll settings, and loopback maximum transmission unit;
- repository commit, topic source prefix, source archive digest, sorted source
  manifests before and after the run, final binary digest, linked-image symbol
  and disassembly evidence, and workspace-gate logs;
- mode, warmup and measured rounds, 1,200-byte segment size, 32 segments per
  batch, sender and receiver CPUs, actual socket buffers, setup and measured
  timer boundaries, send and receive call counts, elapsed and process CPU time;
- logical datagram count, deterministic checksum, expected checksum, full
  payload-verification result, UDP GRO control-message count, maximum segments
  per receive, standard output and error, and process exit status;
- fixed schedule and seed, every attempted process, complete-block inclusion
  decisions, block log contrasts, geometric candidate/scalar ratio, interval,
  block-contrast dispersion, and A/A diagnostic.

## Claim rules

- Loopback can establish socket semantics, syscall shape, kernel-local delivery,
  and the measured host/binary elapsed result. It bypasses the physical NIC,
  DMA, ENA queues, hardware RSS, and wire.
- A device feature flag is capability or configuration evidence. It does not
  prove that the measured packet used the feature.
- One `UDP_GRO` control message plus verified segment reconstruction proves the
  observed socket delivery shape. It does not prove physical-NIC aggregation.
- Linked-image inspection proves that the binary contains the intended call
  paths. It does not prove a kernel branch or device action.
- Internal program call counts are correctness evidence for the harness. A
  system-call tracer is required for an independent call-count observation.
- Elapsed ratios and intervals apply to complete process blocks in one run
  window. They do not generalize from one host to an architecture, processor
  vendor, driver family, or network.
- A/A is a schedule and period diagnostic. It is not a calibrated noise floor
  and does not validate the candidate mechanism.

The 2026-08-05 values in the [topic README](../README.md) are pre-artifact
scratch observations. Do not copy them into a retained exact-source record.

## Exact-source records: pending

Add links here only after both host bundles pass
`experiment/validate_receipts.py`, the final evidence manifests verify, and
each `run.status` reports success:

- Arm loopback record: pending
- runtime-resolved `xxl` loopback record: pending
- cross-host comparison: pending
- raw source-bound bundles: pending

Raw evidence belongs under `raw/<source-prefix>/<host-label>/`. The
[raw evidence contract](raw/README.md) defines the bundle.
