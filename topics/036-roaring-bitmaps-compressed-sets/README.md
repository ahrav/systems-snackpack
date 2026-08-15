# Roaring bitmaps and compressed set representations

Systems store sets of unsigned integer identifiers and repeatedly ask
which identifiers occur in both sets. One representation cannot minimize
space and elapsed time for every distribution. A sorted array fits a tiny set,
a bitmap gives fixed work for a dense chunk, and a run list fits long
consecutive ranges. Roaring selects among local containers so one uneven set
does not pay one global representation cost.

This crate models intersection-cardinality kernels inside one 16-bit chunk. It
is not a production Roaring implementation. It omits the high-key directory,
mixed-container operations, mutation policy, serialization, validation,
concurrency, and 64-bit extensions.

## Mental model

A set's **universe** `U` is the number of possible identifiers. Its
**cardinality** `n` is the number present. Its density is `n / U`. Global
density hides local shape: a globally sparse set can contain both full regions
and isolated values.

Roaring splits a 32-bit identifier into a 16-bit high key and a 16-bit low
value. For `0x1234_abcd`, the high key is `0x1234` and the low value is
`0xabcd`. A sorted directory finds the non-empty high-key chunk. One container
then represents any of the 65,536 possible low values.

The portable format, the cross-implementation byte layout for stored bitmaps,
defines three payload shapes:

- An **array container** stores `k` sorted, unique 16-bit values in `2k` bytes.
- A **bitmap container** stores 1,024 64-bit words in exactly 8,192 bytes.
- A **run container** uses run-length encoding, which stores a consecutive
  interval once. Its payload is `2 + 4r` bytes for `r` runs.

The array and bitmap payloads have equal size at `k = 4,096` because
`2 * 4,096 = 8,192`. This equality does not predict the elapsed-time crossover.
Array intersection follows value-dependent branches, while bitmap intersection
always reads 1,024 word pairs and can use population count, the instruction
that counts set bits. Run storage beats bitmap storage when
`2 + 4r < 8,192`, which holds through 2,047 runs. It beats array storage when
`2 + 4r < 2k`.

For two complete Roaring sets, a useful operation model is:

```text
intersection time
  = directory merge
  + sum(container-pair kernel for each shared high key)
  + result materialization
```

An array-array kernel merges two sorted lists. A bitmap-bitmap kernel applies
bitwise AND and population count to each word pair. A run-run kernel merges
intervals. Mixed pairs need their own algorithms. Counting an intersection can
avoid allocating its members, so it must not be compared directly with an
operation that materializes a result set.

## Representation choices

| Representation | Problem it solves | What it does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- |
| Sorted integer array | Low overhead for few members | Dense scans or cheap mutation | Intersection work grows with the values examined | Chunks stay small and ordered queries dominate |
| Dense bitmap | Fixed direct membership and word-parallel set algebra | A large universe with few members | Pays one bit for every possible value | Chunks are dense or repeated bitwise operations dominate |
| Run-length encoding | Compresses long consecutive ranges | Scattered values | Fragmentation creates many runs and branch-heavy merges | The data naturally contains stable intervals |
| Roaring | Adapts representation independently by 16-bit chunk | Automatic optimality | Conversion, mixed kernels, and directory work remain | Density and run shape vary substantially across chunks |
| Elias-Fano | Near-information-theoretic space for a static sorted sequence | Cheap arbitrary mutation or dense wordwise algebra | Requires the sequence length and a universe bound before encoding | The set is static and ordered access or successor queries dominate |

For a set chosen from `U` possible values, the information lower bound is
`log2(binomial(U, n))` bits, where `binomial(U, n)` counts the possible sets of
`n` distinct values. Sparse sorted encodings approach roughly
`n * log2(U / n) + O(n)` bits by exploiting gaps. A dense bitmap instead uses
`ceil(U / 8)` bytes. A compact Roaring size model is:

```text
bytes = header + directory + sum(container payload) + allocation overhead
```

The payload term depends on each chunk's cardinality and run count, not the
set's global density. A production implementation may preserve its current
container until an explicit optimization pass, so the serialized shape need
not be the minimum of all three formulas after every update.

## Failure boundaries

- Treat identifiers and high keys as unsigned. Test `0`, `2^31 - 1`, `2^31`,
  and `2^32 - 1`; a half-open range ending at `2^32` needs a wider endpoint.
- Keep array values and directory keys sorted and unique. Keep runs sorted,
  non-overlapping, and non-adjacent. Cached cardinalities must match contents.
- Alternating around 4,096 values can repeatedly convert an array and bitmap
  unless the mutation policy uses hysteresis or batches changes.
- Long runs can fragment into costly run lists after scattered updates. Run
  optimization helps only when the resulting representation is smaller or
  improves the measured operation mix.
- A length-bounded deserializer can prevent an out-of-bounds read without
  proving sortedness, cardinality, or other semantic invariants. Validate
  untrusted input before normal operations.
- Portable serialization and a frozen memory view have different lifetime,
  alignment, endianness, and version contracts. Memory mapping does not erase
  those contracts.
- Two valid byte streams can encode the same logical set with different
  container choices. Hash logical values or canonicalize before treating bytes
  as identity.
- Lazy union or exclusive-or may defer cardinality repair. Do not call an API
  that requires exact metadata until the documented repair operation completes.
- A 64-bit Roaring extension commonly maps high 32 bits to 32-bit bitmaps. It
  is a separate interoperability contract, not a wider instance of the 32-bit
  portable format.

## Run the focused experiment

The process harness and disassembly command below require Linux and GNU
binutils. The Rust correctness commands also run on macOS.

From the repository root:

```bash
cargo test --locked --package roaring-bitmaps-compressed-sets

cargo run --locked --release \
  --package roaring-bitmaps-compressed-sets \
  --bin bitmap-probe -- verify

RUSTFLAGS="-C target-cpu=native -C debuginfo=1" \
  cargo build --locked --release \
  --package roaring-bitmaps-compressed-sets \
  --bin bitmap-probe

python3 -I topics/036-roaring-bitmaps-compressed-sets/experiment/run_processes.py \
  --binary target/release/bitmap-probe \
  --blocks 12 \
  --aa-blocks 4 \
  --target-ms 200

objdump -Cd target/release/bitmap-probe | \
  rg -A40 'topic036_(array|bitmap|run)_and_count'
```

Verification prints five `CHECK=PASS` rows. Their exact payload totals for both
inputs are:

```text
CHECK=PASS CASE=tiny16 CARD_A=16 CARD_B=16 AND=8 RUNS_A=16 RUNS_B=12 ARRAY_BYTES=64 BITMAP_BYTES=16384 RUN_BYTES=116
CHECK=PASS CASE=sparse256 CARD_A=256 CARD_B=256 AND=128 RUNS_A=256 RUNS_B=192 ARRAY_BYTES=1024 BITMAP_BYTES=16384 RUN_BYTES=1796
CHECK=PASS CASE=threshold4096 CARD_A=4096 CARD_B=4096 AND=2048 RUNS_A=4096 RUNS_B=3072 ARRAY_BYTES=16384 BITMAP_BYTES=16384 RUN_BYTES=28676
CHECK=PASS CASE=dense32768 CARD_A=32768 CARD_B=32768 AND=16384 RUNS_A=32768 RUNS_B=1 ARRAY_BYTES=131072 BITMAP_BYTES=16384 RUN_BYTES=131080
CHECK=PASS CASE=runs64 CARD_A=32768 CARD_B=32768 AND=16384 RUNS_A=64 RUNS_B=64 ARRAY_BYTES=131072 BITMAP_BYTES=16384 RUN_BYTES=516
```

The Linux harness pins itself to one available central processing unit (CPU).
It runs 12 fresh-process candidate-versus-bitmap pairs per case and alternates
`AB` and `BA` order, where `A` is the candidate and `B` is the bitmap baseline.
It reports the median and inclusive interquartile range (IQR) of the 12
candidate/bitmap ratios. Four fresh-process bitmap/bitmap pairs exercise the
same schedule and analysis path. The default run launches 128 timed processes
and ends with:

```text
CHECK=PASS BLOCKS=12 AA_BLOCKS=4 PROCESSES=128
```

Input construction, correctness checks, calibration, warmup, output, and
process startup stay outside `ELAPSED_NS`. `EXTERNAL_WALL_NS` includes those
costs. Each row is a fresh-process measurement; repeated kernel calls inside a
process are subsamples. The paired process block is the analysis unit. The IQR
covers variation among those 12 blocks on one host in one run window. It does
not cover other CPUs, compilers, corpora, or workloads.

The experiment tests isolated, warm intersection-cardinality kernels for five
synthetic chunk shapes. It does not test a production Roaring implementation,
mixed-container dispatch, allocation, serialization, updates, cache-cold
queries, or end-to-end indexes. Disassembly proves the linked instruction shape
only. It cannot by itself prove which instruction caused an elapsed-time
difference. See [`measurements/README.md`](measurements/README.md) for the raw
evidence contract.

## Exact-source Linux result

Both required hosts built and ran source archive
`43919a031a53d6ddef976d7e2ec4bf55fed565984c79181568925b01d83230a1`.
Generic and native correctness checks passed. Each timing estimate below uses
12 paired, order-balanced fresh-process blocks. The interval is the inclusive
interquartile range across those block ratios.

| Candidate / bitmap | Arm median [IQR] | x86-64 median [IQR] |
| --- | ---: | ---: |
| `tiny16` array / bitmap | 0.151670505 [0.151076804, 0.153327777] | 0.196955641 [0.196794020, 0.197091033] |
| `sparse256` array / bitmap | 2.422791478 [2.421387675, 2.428848938] | 3.075839376 [3.072346450, 3.083156901] |
| `threshold4096` array / bitmap | 37.730651404 [37.615466572, 37.812116275] | 47.486844057 [47.342032453, 48.105404568] |
| `dense32768` array / bitmap | 196.660606170 [196.532671710, 197.240854791] | 310.111693569 [307.208858259, 312.259022479] |
| `runs64` run / bitmap | 2.520290876 [2.518226871, 2.523743425] | 2.878707445 [2.870126234, 2.892766912] |
| bitmap / bitmap A/A, four blocks | 1.000740707 [1.000093298, 1.001148512] | 0.998624744 [0.997412161, 1.003285833] |

The literal Arm host reported AArch64 and used an SVE vector bitmap kernel. The
`xxl` alias resolved to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, which
reported x86-64 and used AVX2-width AND plus AVX-512 VPOPCNTDQ population count.
The ratios differ between these two linked artifacts. They do not establish an
architecture-wide comparison. The direction agreed on both hosts: the tiny
array won, while the larger arrays and 64-run input lost to the bitmap kernel.

See the [Arm receipt](measurements/2026-08-15-arm64/README.md) and
[x86-64 receipt](measurements/2026-08-15-x86-64/README.md) for exact host,
binary, raw-process, and disassembly evidence.

## Primary sources

- Lemire, Ssi-Yan-Kai, and Kaser, [Consistently faster and smaller compressed bitmaps with Roaring](https://arxiv.org/abs/1603.06549), including run containers and pair-specific operations.
- Roaring maintainers, [Roaring bitmap portable format specification](https://github.com/RoaringBitmap/RoaringFormatSpec), for unsigned ordering, payload layouts, cookies, and valid alternate encodings.
- Lemire et al., [Roaring Bitmaps: Implementation of an Optimized Software Library](https://arxiv.org/abs/1709.07821), for CRoaring's vectorized kernels and benchmark boundary.
- Wu et al., [Optimizing bitmap indices with efficient compression](https://sdm.lbl.gov/~kewu/ps/LBNL-49626-tods.pdf), for Word-Aligned Hybrid run-length encoding.
- Vigna, [Quasi-succinct indices](https://vigna.di.unimi.it/ftp/papers/QuasiSuccinctIndices.pdf), for the Elias-Fano space and query model.
- Roaring Rust maintainers, [`roaring` 0.11.5 source release](https://github.com/RoaringBitmap/roaring-rs/releases/tag/v0.11.5), for the current source boundary. During this run, docs.rs still served 0.11.4 as `latest`; inspect the resolved package before applying version-specific API claims.
