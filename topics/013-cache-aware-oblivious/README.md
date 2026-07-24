# Cache-aware and cache-oblivious layout

Locality has two separate dimensions:

1. **Transfer locality:** how many cache-line transfers occur across a cache
   boundary.
2. **Placement locality:** which cache sets must hold those lines at the same
   time.

Cache-aware blocking and cache-oblivious recursion are techniques for reducing
those transfers. Neither by itself proves set occupancy on a
finite-associativity cache.

## Cost model

The ideal-cache model has a cache of `Z` words and lines of `B` words. It
assumes optimal replacement and measures line transfers. A cache-oblivious
algorithm does not name `Z` or `B`; a cache-aware algorithm chooses a tile or
node size from them. Under the tall-cache assumption `Z = Omega(B^2)`, both
blocked and recursive matrix transpose can attain:

```text
Theta(1 + N^2 / B)
```

transfers for an `N x N` matrix. The bound does not include set associativity,
TLBs, prefetching, memory-level parallelism, coherence, or NUMA placement.

For a cache with line size `L`, `S` sets, and `W` ways:

```text
capacity = L * S * W
simple_set(address) = floor(address / L) mod S
```

If a traversal advances by `d` cache lines, the simple modulo model visits:

```text
S / gcd(S, d)
```

sets before repeating. A power-of-two leading dimension can therefore use only
a fraction of the sets even when the total working set fits. This is a
hypothesis generator, not a portable address-to-set contract. Real processors
may hash address bits, skew banks, or select shared-cache slices with
undocumented functions.

The closed form requires an integer-line stride. For a non-integral stride such
as 2,049 `u64` elements with 64-byte lines, analyze
`floor((base_offset + k * stride_bytes) / L) mod S`; the cycle also depends on
the base offset.

The elapsed-time model is also conditional:

```text
T = work * compute_cost
  + line_fills * exposed_fill_cost
  + translation_walks * exposed_walk_cost
  + coherence_and_queueing
```

`exposed_fill_cost` depends on overlap, prefetching, bandwidth, and queue
occupancy. Multiplying a miss counter by a nominal latency is not an elapsed
time prediction.

## Technique selection

| Technique | Control | Strength | Main failure mode |
| --- | --- | --- | --- |
| Flat scalar traversal | none | simple, predictable code | strided dimension may waste lines and sets |
| Cache-aware tiling | explicit tile size | low overhead near one known cache level | one tile is rarely best for every level and host |
| Cache-oblivious recursion | recursive subdivision | multilevel transfer locality without cache constants | recursion, cutoff, layout, and finite associativity still matter |
| Padding or alignment skew | leading dimension or base offset | can break harmful modulo periods | virtual offsets do not prove physical shared-cache placement |
| Cache-aware tree node | explicit fanout | high line utilization for one target | page and deeper-cache costs can dominate |
| van Emde Boas or cache-oblivious tree layout | recursive parameter-free layout | model-specific search-transfer bounds without embedding `B` in the layout | rebuild complexity and branch/code costs can erase the gain |

One practical design is hybrid: use a recursive decomposition for coarse
multilevel locality, stop at a fixed small leaf, and run a compact cache-aware
kernel inside the leaf. Measure several leading dimensions and base alignments
instead of tuning one lucky allocation.

## Transpose artifact

This crate provides three square transpose kernels:

- `transpose_naive` scans each input row and writes one strided output column.
- `transpose_tiled` uses an explicit square tile.
- `transpose_recursive` bisects the larger region until a fixed leaf area, then
  executes the same scalar operation.

All kernels accept a leading dimension greater than the logical matrix size.
This declares `ld = 2048` versus `ld = 2049` as the layout perturbation while
holding logical element count constant. Separate processes still vary
allocation placement, so the ratios are not identical-placement pairs. The
correctness oracle compares every logical element and verifies that the
recorded padded mode leaves each destination padding element untouched.

```bash
cargo run -p systems-snackpack-topic-013 --example check_contracts
cargo bench -p systems-snackpack-topic-013 --bench cache_layout -- \
  b01-p1 1 1 pow2-naive
```

The benchmark reports combined setup and conditioning (`setup_ns`), the kernel
(`kernel_ns`), and verification (`verify_ns`) separately. The runner also
records whole-process elapsed time. Only `kernel_ns` supports the layout
comparison. The checksum is computed afterward so the compiler cannot discard
the stores.

## Physical-address boundary

With base pages, virtual and physical addresses share only the page offset.
For a conventional VIPT L1 cache whose set-index bits fit inside that offset,
same virtual page offsets can predict an L1 set candidate. They do not reveal a
physical shared-cache set or slice.

Since Linux 4.0, page-frame disclosure through `/proc/PID/pagemap` requires
`CAP_SYS_ADMIN`. Linux 4.0 and 4.1 reject unprivileged opens; Linux 4.2 and
later can allow the read while zeroing every PFN. The experiment records the
observed outcome rather than converting virtual addresses into invented
physical colors. `MADV_HUGEPAGE` is advice, not proof. For PMD-sized anonymous
THP, inspect the mapping's `AnonHugePages`; do not infer larger physical-offset
guarantees for multi-size THP from `smaps` alone.

## Failure controls

- A lower elapsed time does not identify compulsory, capacity, or conflict
  misses. The modulo model, leading-dimension perturbation, cache geometry, and
  generated code provide converging evidence, not proof of replacement state.
- A matrix row stride can trigger prefetch, TLB, bank, or load/store
  disambiguation effects. Use a dependency-chained workload when isolating load
  latency.
- One process with many inner repetitions does not sample allocator placement
  or operating-system noise. The recorded run uses fresh processes and treats
  each process as one replicate.
- Sequential A-then-B runs confound layout with drift. The runner uses
  order-balanced blocks and derives paired ratios within each block.
- Compiler transformations can make source-level variants incomparable. Retain
  linked disassembly and checksums for the measured binary.
- Host cache geometry describes capacity and sharing, not an undocumented index
  hash. Conclusions remain scoped to the recorded host, kernel, toolchain,
  flags, binary, and input.

## Focused Linux experiment

The recorded runner supports Linux `x86_64` and AArch64 hosts with GNU
`taskset` and binutils, 4,096-byte base pages, and 64-byte data-cache lines. It
fails closed otherwise.

Create a gzip-compressed archive from a committed source candidate and run the
same bytes on each host:

```bash
commit=$(git rev-parse HEAD)
git archive --format=tar.gz --output=/tmp/topic13.tar.gz "$commit"
archive_sha=$(sha256sum /tmp/topic13.tar.gz | awk '{print $1}')

SOURCE_ARCHIVE=/tmp/topic13.tar.gz \
  topics/013-cache-aware-oblivious/experiment/run_processes.sh \
  /absolute/output requested-host "$commit" "$archive_sha" 0 12
```

The runner:

1. verifies the archive bytes and embedded commit;
2. runs the workspace gates from the extracted tree;
3. records architecture, CPU model, cache geometry, CPU count, kernel,
   toolchains, target features, base-page size, THP and ASLR policies, and
   pagemap visibility;
4. builds one release benchmark binary and records its checksum and
   disassembly;
5. runs 12 order-balanced blocks, with one pinned fresh process for each of the
   six layout modes per block;
6. rejects missing, duplicate, reordered, misconfigured, or checksum-divergent
   rows before calculating medians, interquartile ranges, sample standard
   deviations, and within-block paired ratios.

The six modes are the three kernels at `N = 2048` with `ld = 2048` and
`ld = 2049`. Each process performs a 128 MiB conditioning sweep before its
kernel. Combined setup and conditioning, process startup, and checksum
verification are outside the kernel interval and remain in the raw record.

Read the [first-visit note](rounds/01.md), [primary-source
ledger](references.md), [measurement contract](measurements/README.md), and
[two-host results](measurements/2026-07-23-cross-host.md).
