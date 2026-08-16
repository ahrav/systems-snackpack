# Primary sources and version boundaries

Format specifications define wire semantics. A Request for Comments (RFC) is a
document in the archival RFC Series for Internet technical specifications,
research, and standards; not every RFC originates in the Internet Engineering
Task Force or is standards-track. [RFC 8729](https://www.rfc-editor.org/rfc/rfc8729.html)
defines that publication model. Tagged headers and source define library
behavior. Host receipts name the older runtime packages used by the focused
experiment. Project benchmark tables do not rank codecs for another corpus,
unit size, or machine.

## Formats and application programming interfaces (APIs)

- [Zstandard format, RFC 8878](https://www.rfc-editor.org/rfc/rfc8878)
  defines frames, dependent blocks, windows, optional checksums, and dictionary
  identifier fields. It explicitly omits generic random access.
- [Hypertext Transfer Protocol (HTTP) zstd, RFC 9659](https://www.rfc-editor.org/rfc/rfc9659)
  limits encoded windows to 8 mebibytes (MiB) and requires decoder support
  through 8 MiB.
- [zstd 1.5.7 API](https://github.com/facebook/zstd/blob/v1.5.7/lib/zstd.h)
  defines compression bounds, level and context APIs, stream-completion results,
  window limits, and dictionary object contracts.
- [zstd 1.5.7 seekable format](https://github.com/facebook/zstd/blob/v1.5.7/contrib/seekable_format/zstd_seekable_compression_format.md)
  defines independent frames plus a skippable-frame seek table.
- [LZ4 1.10.0 frame format](https://github.com/lz4/lz4/blob/v1.10.0/doc/lz4_Frame_format.md)
  separates block independence from indexing and defines optional block and
  content checksums plus the frame's uncompressed-block fallback.
- [LZ4 1.10.0 block API](https://github.com/lz4/lz4/blob/v1.10.0/lib/lz4.h)
  defines caller-provided sizes, bounds, and safe decode behavior.
- [DEFLATE, RFC 1951](https://www.rfc-editor.org/rfc/rfc1951.html)
  defines the 32 kibibyte (KiB) history and cross-block references.
- [gzip, RFC 1952](https://www.rfc-editor.org/rfc/rfc1952)
  defines member framing, a 32-bit cyclic redundancy check (CRC-32),
  modulo-`2^32` decoded size, and concatenation.
- [Brotli, RFC 7932](https://www.rfc-editor.org/rfc/rfc7932.html) defines regular
  Brotli windows and decoder resource-limit considerations;
  [RFC 9841](https://www.rfc-editor.org/rfc/rfc9841.html) extends Brotli with
  shared dictionaries, large-window streams, and framing.
- [XZ file format 1.2.1](https://tukaani.org/xz/xz-file-format.txt) and
  [XZ Utils 5.8.3](https://github.com/tukaani-project/xz/releases/tag/v5.8.3)
  define the container and current upstream implementation boundary.
- [Snappy 1.2.2 raw format](https://github.com/google/snappy/blob/1.2.2/format_description.txt)
  and [framing format](https://github.com/google/snappy/blob/1.2.2/framing_format.txt)
  separate raw blocks from checksummed chunks.

## Transport contracts

- [HTTP semantics, RFC 9110](https://www.rfc-editor.org/rfc/rfc9110.html)
  defines content coding, `Accept-Encoding`, cache variation, and shared-context
  compression risks.
- [Transport Layer Security (TLS) 1.3, RFC 9846 section 5.4](https://www.rfc-editor.org/rfc/rfc9846.html#section-5.4)
  defines optional record padding that can make ciphertext length less directly
  informative; length secrecy is not automatic.
- [gRPC over HTTP/2](https://github.com/grpc/grpc/blob/master/doc/PROTOCOL-HTTP2.md)
  and [gRPC compression behavior](https://github.com/grpc/grpc/blob/master/doc/compression.md)
  define per-message compression and negotiation. These are living documents;
  implementation support remains language- and version-specific.

## Measurement method

- [United States National Institute of Standards and Technology (NIST)
  randomized block designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
  explain blocking known nuisance factors before randomizing remaining order.
- [NIST confidence interval for a mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)
  defines the Student-t mean interval used for each marginal block-log-ratio
  summary; it is not a prediction interval for future processes.
- [The Ordering Trap, USENIX Annual Technical Conference 2023](https://www.usenix.org/conference/atc23/presentation/duplyakin)
  shows that prior trials and layout can influence later measurements.
- [`sched_getaffinity(2)`](https://man7.org/linux/man-pages/man2/sched_getaffinity.2.html)
  and the [Linux cgroup v2 cpuset documentation](https://docs.kernel.org/admin-guide/cgroup-v2.html#cpuset)
  define the affinity and granted-processor evidence recorded by the runner.
- [`clock_gettime(2)`](https://man7.org/linux/man-pages/man2/clock_gettime.2.html)
  defines the Linux monotonic clocks used by the native probe.
- [GNU `objdump`](https://sourceware.org/binutils/docs/binutils/objdump.html)
  defines the static object-file disassembly used for linked-call-site
  inspection; it does not show which branch executed.
- [Steele, Lea, and Flood's SplitMix paper](https://dl.acm.org/doi/10.1145/2660193.2660195)
  defines the deterministic generator used for the repeatable pseudorandom
  control; observed stored bytes, not the generator name, establish whether a
  tested codec expands that corpus.

## Model boundary

The break-even, unit-amplification, memory, and admission equations are
analytical models derived in this topic. The cited zstd 1.5.7 and LZ4 1.10.0
APIs do not expose these combined equations as runtime predictors; they expose
narrower bounds and resource controls. The experiment records and hashes the
runtime shared libraries on each retained host. Tagged 1.5.7 and 1.10.0 sources
above define the current upstream comparison boundary.
