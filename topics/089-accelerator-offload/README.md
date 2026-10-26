# Accelerator offload economics

The executable models three independent FIFO engines, reusable buffer slots,
and H2D -> compute -> D2H dependencies. Supplied durations are assumptions.
The CPU probe compares element-major and round-major execution of the same
unsigned 32-bit transform. It establishes CPU baselines for an offload decision.

```bash
cargo test -p accelerator-offload
cargo build --release -p accelerator-offload
python3 topics/089-accelerator-offload/scripts/oracle.py target/release/accelerator-offload
SOURCE_COMMIT=$(git rev-parse HEAD) python3 topics/089-accelerator-offload/scripts/measure.py target/release/accelerator-offload /tmp/offload-results
```

Expected oracle output: 4,500 scheduling cases and 50 transform cases pass.
For eight ready batches with stage costs `[4, 2, 4]`, one, two and three slots
finish at 80, 44 and 38 time units. Each slot stays occupied through output
transfer completion. The Python oracle advances ticks and dispatches ready
operations; the Rust scheduler computes earliest start times directly.

A serialized request includes batch wait, device queue wait, host preparation,
input copies, launch, kernel, output copies, and result handling. The schedule
model covers the three engine stages only. A shared bidirectional copy engine,
variable durations, arrivals, host submission cost, and resource contention
require a different model. Zero-duration stages are supported; time overflow
and zero slots return errors.

The exact transform is `(x ^ (x >> 13)) * 1664525 + 1013904223` modulo 2^32.
Element-major completes all rounds before writing each output. Round-major
copies the input, then updates adjacent elements each round. The benchmark
uses one thread, preallocated buffers, one untimed warmup per fresh process,
and ten process pairs per shape with five AB and five BA orders. It measures
warm-buffer transform execution; allocation and result checksum are outside
that interval. It includes round-major's required initial copy. Both variants
write a complete output array and preserve the input.

Shapes are 256, 65,536 and 1,048,576 elements at 1 and 32 rounds. Repeat counts
are `max(1, min(10000, 2000000 // (n * rounds)))`. Linux processes pin to the
first allowed CPU. Frequency, thermals, SMT siblings and host load remain
uncontrolled. The independent Python integer oracle checks every timed
shape's checksum. Smaller fixtures compare every output value.

The declared descriptive winner rule requires all ten paired ratios to favor
one variant by over 5%. A practical tie requires every ratio within the
reciprocal 5% band. Other cells remain unresolved. This rule makes no
population-level significance claim. Keep raw rows and variability.

See [results](measurements/results.md) for source identity, observations, and
device limits, and [sources](sources.md) for primary references. The complete
teaching transcript and inspected visual are retained outside this repository.
