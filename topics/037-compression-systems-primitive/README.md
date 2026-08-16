# Compression as a systems primitive

Compression trades central processing unit (CPU) and memory work for fewer
stored or transmitted bytes. It helps only when the saved byte-path cost
exceeds encode, decode, allocation, copy, and queueing costs. The independently
decodable unit, raw fallback, index, integrity, decoder limits, compatibility,
and rollout are part of the design.

This crate models those decisions. Its Linux probe compares 1,024 independent
256-byte units with one 256-kibibyte batch over the same logical input. One
kibibyte (KiB) is 1,024 bytes. This is not a production codec wrapper or a
codec ranking.

## Mental model

A **codec** is an encoder, decoder, and byte-format contract. A **frame** is a
recognizable envelope with a beginning, end, and parameters. A frame may
contain blocks that still depend on earlier decoded state. A compression ratio
in this topic is:

```text
R = uncompressed bytes / stored compressed bytes
```

`R > 1` means the representation shrank. Stored bytes include framing and
index metadata when those layers are present.

**History** is earlier content that a codec may reference instead of writing
the same bytes again. A **dictionary** is pre-shared history supplied outside
the current payload. An **independent unit** does not depend on earlier data
units; it may still require separately identified codec parameters or a
pre-shared dictionary. A separate index is also needed to locate that unit.

Compression design has seven parts:

1. Select raw or compressed representation, codec, level, and parameters.
2. Choose the independent record, message, page, chunk, batch, or object unit.
3. Locate that unit with trusted offsets and sizes when random access matters.
4. Bound CPU, memory, output, temporary storage, and concurrent decoders.
5. Require complete decode and protect payload plus metadata integrity.
6. Negotiate reader support and immutable dictionary identity.
7. Deploy readers before writers and retain every historical dependency.

Raw is one valid adaptive representation. Tiny, random, encrypted, and
already-compressed payloads can expand.

## Technique boundaries

| Technique | Problem solved | What it does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- |
| Raw or identity | Avoids codec work and expansion | Byte-path pressure | Uses the full byte count | Compression does not earn its total cost |
| LZ4 or Snappy, fast Lempel-Ziv-family codecs | Low codec cost for frequently executed paths | Smallest output, indexing, or authentication | Raw-block and framed contracts differ | Request, cache, or page latency dominates |
| Zstandard (zstd) | Many speed-versus-size settings | Generic random access or safe application limits | Level, window, dictionary, checksum, and library call path matter | Storage or network bytes constrain the path |
| gzip and its DEFLATE stream format | Deployed compatibility | Independent DEFLATE-block seeking | History crosses block boundaries | Existing readers require gzip |
| Brotli or XZ | Small output for data encoded once | Dynamic request latency | Encode CPU and memory can be high | Static assets or cold archives justify it |
| Batching | Amortizes setup, framing, and history reset | Independent point access | Read and recovery amplification grow | Records are consumed together |
| Trained dictionary | Shared history for small independent records | Distribution, retention, or authentication | The dictionary becomes immutable versioned data | Stable record families must remain independent |
| Type-aware transform | Exposes numeric or run structure | General data reduction | Noisy inputs can grow | Column statistics justify a reversible transform |

An independent unit is not randomly accessible until a trustworthy index maps
logical positions to compressed offsets and sizes. Zstd frames and
independently encoded LZ4 raw blocks define decode boundaries once required
dictionaries, parameters, and sizes are available; they do not provide the
index that locates a unit.

## Cost model

Let:

- `S` be uncompressed bytes;
- `R` be `S / compressed_bytes`;
- `B` be effective raw input/output (I/O) byte-path bandwidth in bytes per second;
- `E` and `D` be encode and decode speed in uncompressed bytes per second;
- `F` be fixed per-unit setup and framing time; and
- `A` be added allocation, copy, and queueing time.

For a serial write:

```text
raw_time        = S / B
compressed_time = F + S / E + S / (R * B) + A
```

Compression reduces elapsed time only when:

```text
F + S / E + A < (S / B) * (1 - 1 / R)
```

For `S > 0` and `R > 1`, ignoring fixed and added costs gives the
screening threshold:

```text
E > B * R / (R - 1)
```

Use `D` for a read. Include both terms for a round trip. With ideal pipeline
overlap, useful write throughput is approximately `min(E, R * B)` and useful
read throughput is `min(D, R * B)`. These equations filter candidates; they do
not predict queueing, cache pressure, contention, or slow-request latency.

For `0 < q <= u`, when a request for `q` decoded bytes lies wholly within one
full independent unit of `u` bytes and decoding materializes that whole unit,
decode amplification is `u / q`. Increasing the unit size exposes more history
and spreads fixed costs across more bytes, but the resulting ratio depends on
the data and codec. Decreasing it bounds point-read work, retry scope, working
memory, and corruption scope while creating more units to schedule.

The library exposes checked models for byte selection, serial-path break-even,
decode amplification, and decoder admission. Run its doctests and tests with:

```bash
cargo test --locked --package compression-systems-primitive
```

## Integrity and hostile input

Codec parsing and checksums do not authenticate an object. Native checks vary
by format, can be optional, and may validate only after the decoder has emitted
bytes. Protect codec identifiers, dictionary identities, offsets, sizes, and
ordering as well as payload bytes.

For every untrusted decode:

- cap compressed input and absolute decoded output;
- cap history window, dictionary, and aggregate nested memory;
- enforce a deadline or cancellable work budget;
- cap frame, chunk, index, and nesting counts;
- cap temporary storage and concurrent decoders;
- require representation-specific completion: a complete-frame result for a
  framed stream, or exact input and output boundary checks for a raw block; and
- publish decoded bytes only after required integrity checks pass.

An expansion-ratio cap is secondary. A declared decoded size is untrusted
metadata and never bypasses the caller's absolute limit.

Transport Layer Security (TLS) does not inherently hide encoded length;
ciphertext lengths remain observable unless record padding or traffic shaping
obscures them. Do not share one compression context between attacker-controlled
guesses and secrets.

## Focused Linux experiment

The probe uses the same 262,144-byte input in every treatment:

- `structured`: 1,024 log-shaped records with repeated fields and changing identifiers;
- `random`: bytes from the deterministic SplitMix64 pseudo-random generator,
  used as a repeatable control expected to resist these codecs;
- `independent`: 1,024 separately encoded 256-byte units; and
- `batch`: one 256 KiB unit.

Treatments are identity, raw LZ4 blocks with an explicit length field, and zstd
level 1. Every timed process verifies the decoded bytes. Encode and decode have
separate clocks. Corpus construction, allocation, calibration, and warmup stay
outside those clocks.

On Linux, run correctness and the fresh-process comparison from the repository
root:

```bash
cargo run --locked --release \
  --package compression-systems-primitive \
  --bin compression-contract-probe -- verify

bash topics/037-compression-systems-primitive/experiment/build_probe.sh \
  /tmp/topic037-probe

python3 -I \
  topics/037-compression-systems-primitive/experiment/run_processes.py \
  --binary /tmp/topic037-probe/compression-probe \
  --source topics/037-compression-systems-primitive/experiment/compression_probe.c \
  --validator topics/037-compression-systems-primitive/experiment/validate_receipts.py \
  --output /tmp/topic037-results \
  --blocks 12 \
  --aa-blocks 4 \
  --target-ms 200

python3 -I \
  topics/037-compression-systems-primitive/experiment/validate_receipts.py \
  /tmp/topic037-results
```

The output directories must not exist. Twelve complete order-balanced blocks
provide the treatment estimates. Four same-method blocks check the schedule and
analysis path. Inner codec calls reduce timer noise; they do not increase the
number of fresh treatment applications or complete-block contrasts.

Inspect linked call sites with:

```bash
objdump -drwC --disassemble=topic037_encode_all \
  /tmp/topic037-probe/compression-probe |
  rg 'ZSTD_compress|LZ4_compress|memcpy'

objdump -drwC --disassemble=topic037_decode_all \
  /tmp/topic037-probe/compression-probe |
  rg 'ZSTD_decompress|LZ4_decompress|memcpy'
```

External call sites confirm that the wrapper contains the expected codec
calls. They do not prove which branch ran, identify a shared library's
internal instruction path, or explain an elapsed-time difference.

## Evidence boundary

- **Measured:** input and stored bytes, encode and decode elapsed time, external
  wall time, process order, checksums, host and toolchain metadata, executable
  and library digests, and linked call sites.
- **Derived:** throughput, complete-block log contrasts, geometric ratios,
  sample dispersion, raw-fallback decisions, and analytical break-even points.
- **Source-backed:** format and library-interface behavior in
  [`references.md`](references.md).
- **Inferred:** fixed-call, history-reset, cache, branch, and vector mechanisms
  unless a separate observation isolates them.
- **Not tested:** production data, storage or network I/O, dictionaries,
  contention, 99th-percentile latency, energy, or generality across an
  instruction-set architecture or vendor family.

See [`rounds/01.md`](rounds/01.md) for the promotion contract and
[`measurements/README.md`](measurements/README.md) for the measurement contract
and retained host evidence.

## Selection guide

1. Record corpus and size distributions, access pattern, read/write ratio,
   bottleneck, latency targets, trust boundary, secrecy, and oldest reader.
2. Keep raw in the candidate set and require a total-byte or end-to-end win.
3. Align the compression unit with a natural read, write, retry, or recovery unit.
4. Sweep a bounded codec, level, unit-size, and dictionary set.
5. Measure encode, decode, total bytes, memory, and tails under real contention.
6. Protect and validate indexes, sizes, codec tags, and dictionary identities.
7. Test empty, tiny, random, compressed, maximum, truncated, corrupted,
   trailing, concatenated, and wrong-dictionary inputs.
8. Deploy readers first and retain old representations through the data horizon.
