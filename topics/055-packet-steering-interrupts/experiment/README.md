# Cross-host steering experiment

This Linux-only experiment checks UDP integrity and receive-placement
observations across two non-loopback interface routes. It compares one live flow
with 128 live flows while holding each process at 256 request and echo pairs.
It is a correctness and topology experiment. It makes no throughput or latency
claim.

## Design

Treatment A uses one connected client socket for 256 sequential request and
echo pairs. Treatment B opens 128 distinct connected client sockets before
sending and gives each socket two sequential pairs. Every payload carries its
flow and sequence identity plus a checksum. The server rejects duplicate,
missing, corrupt, or out-of-range packets. It also requires one distinct source
endpoint per flow.

The campaign has four order-balanced blocks:

```text
ABBA
BAAB
ABBA
BAAB
```

Two more blocks run the identical many-flow operation under labels X and Y:

```text
XYYX
YXXY
```

Every period runs Arm receive plus x86-64 echo receive, then the reverse
direction. All 24 periods use fresh server and client processes. Inner packets
are correctness workload, not independent samples. No elapsed value is used.

The connected client sockets expose an incoming CPU and NAPI-ID socket snapshot
for each echoed flow. On the pinned v6.12 path, those fields are updated before
enqueue and are not metadata bound to the exact datagram later read. Valid
NAPI-ID retrieval also depends on `CONFIG_NET_RX_BUSY_POLL`. The unconnected,
wildcard-bound shared server marks NAPI only once and does not continuously
update incoming CPU, so it cannot expose a valid per-flow CPU mapping through
these options. Its flow records prove peer identity and packet completeness
only; its CPU and NAPI values are shared-socket diagnostics.

## Frozen source

Commit the topic before running the final campaign. Build a path-limited Git
archive whose only non-parent members are under this topic:

```bash
git archive \
  --format=tar.gz \
  --prefix="systems-snackpack-${SOURCE_COMMIT}/" \
  --output="$SOURCE_ARCHIVE" \
  "$SOURCE_COMMIT" \
  topics/055-packet-steering-interrupts
sha256sum "$SOURCE_ARCHIVE"
```

Transfer that archive and a separate byte-identical copy of the archived
`run_host.sh` to each required host. The `prepare` operation rejects an
unexpected host or architecture, an archive with any non-topic file, a source
hash mismatch, or a runner mismatch. It compiles with:

```text
--edition 2024 -D warnings -C opt-level=3 -C debuginfo=1
-C target-cpu=generic -C overflow-checks=yes
```

It also runs the model unit tests, doctests, and example on the exact host. It
records source, binary, ELF, dynamic-call, route, queue, driver, `ethtool`, IRQ
affinity, interrupt, steering-map, and softnet evidence.

Prepare each fresh receipt:

```bash
SOURCE_COMMIT=<40 lowercase hex>
SOURCE_ARCHIVE_SHA256=<64 lowercase hex>

ssh "$ARM_HOST" "$ARM_RUNNER prepare $ARM_RECEIPT arm \
  dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com aarch64 \
  $SOURCE_COMMIT $SOURCE_ARCHIVE_SHA256 $ARM_ARCHIVE"

ssh "$X86_HOST" "$X86_RUNNER prepare $X86_RECEIPT xxl \
  $X86_RUNTIME_HOST x86_64 \
  $SOURCE_COMMIT $SOURCE_ARCHIVE_SHA256 $X86_ARCHIVE"
```

Run both directions and seal the receipts:

```bash
experiment/run_cross_host.sh \
  "$ARM_HOST" "$ARM_RUNNER" "$ARM_RECEIPT" "$ARM_IPV4" \
  "$X86_HOST" "$X86_RUNNER" "$X86_RECEIPT" "$X86_IPV4"
```

The controller refuses a loopback route. The sealer requires all 48 local
probe outputs, empty stderr, exact source identity, 256 observations per
process, complete peer identities, and stable known CPU plus positive NAPI
values on every connected client flow. It does not interpret the shared server
socket as per-flow placement.

Retrieve each read-only receipt with modes preserved. Validate it independently:

```bash
python3 experiment/validate_receipt.py \
  "$RECEIPT" "$LABEL" "$HOSTNAME" "$ARCHITECTURE" \
  "$SOURCE_COMMIT" "$SOURCE_ARCHIVE_SHA256"
```

The validator reconstructs the plan and semantic counts. It verifies the
path-limited archive, source and binary hashes, output roles, complete unique
flow IDs, per-flow packet counts, connected-client CPU and NAPI observations,
server peer uniqueness, route interface, queue inventory, unchanged steering
and IRQ-affinity configuration, manifest coverage, hashes, file kinds, and
read-only seal.

## Evidence limits

- Positive NAPI identifiers do not reveal an RSS key, hash fields, or
  indirection entry.
- Multiple NAPI identifiers do not prove CPU fanout, RSS as the unique cause,
  or a one-to-one queue/NAPI mapping.
- A stable flow placement does not prove which hardware hash caused it.
- A shared server socket's incoming CPU and NAPI values are socket-wide
  diagnostics, not per-flow observations.
- Interrupt deltas include ambient work and interrupt moderation. They are not
  packet counts.
- Zero RPS/RFS files exclude classic generic RPS and software RFS on the
  inspected ingress queues. They do not exclude redirects or another device or
  driver path. Zero XPS map files exclude only those map families, not every driver
  TX-queue selection policy. They do not prove a universal default.
- A missing or unsupported `ethtool` query remains missing capability evidence.
- The two hosts differ in far more than instruction set. Cross-host differences
  do not establish architecture or vendor effects.
