# Measurement contract

This topic retains correctness, process-order, elapsed-time, topology, and
generated-code evidence for one flat trie and one exact minimal deterministic
acyclic finite-state acceptor (DAFSA).

## Required records

Each promoted host record names:

- the exact source commit and shared source-archive Secure Hash Algorithm
  256-bit (SHA-256) digest;
- the Secure Shell (SSH) target, alias where applicable, configured backing
  hostname, resolved remote hostname, architecture, kernel, central processing
  unit (CPU), and available CPU count;
- Rust, Cargo, C compiler, binary-tools, target features, build flags,
  affinity, and binary digest;
- generic and native correctness outcomes;
- stable corpus, query, result, state, arc, and topology-byte metadata;
- the frozen repetition map and deterministic process schedule;
- every process row, exit status, and external wall time;
- 12 complete-block contrasts per data set;
- four same-method schedule-check blocks, kept separate;
- independent receipt validation; and
- linked lookup symbol and disassembly.

## Interpretation

Elapsed time measures the exact executable, inputs, host, affinity, and run
window. The candidate-to-baseline ratio compares methods inside that window.
Its sample standard deviation covers variation among complete block contrasts,
not other machines, compilers, corpora, or future runs. Inner repetitions do
not increase the independent run count.

Generated instructions establish linked code shape. They do not prove a cache,
branch, page-fault, or instruction-throughput cause. Host model and feature
flags identify the measured system; they do not support an instruction-set or
vendor-family ranking.

`topology_bytes` counts state and arc records. It excludes source keys, queries,
builder storage, allocator metadata, vector capacity, resident memory, and file
bytes.

Raw logs use one compressed archive per required host. An outer `SHA256SUMS`
file verifies each retrieved archive.

## Retained exact-source result

The retained source is commit
`7c9a4c3c20e0152d58c30da66dde418b2c71ab40`. Both hosts received the same
archive with SHA-256 digest
`ded13d382acdcc3b5487c38965cd099ab7b36024071d81518bdff24b3261389b`.

| SSH target | Resolved host | Architecture and CPU evidence | Kernel | Available CPUs |
| --- | --- | --- | --- | ---: |
| `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | same literal host | `aarch64`; Arm implementer `0x41`, part `0xd40`, revision 1 | `6.12.95-124.187.amzn2023.aarch64` | 64 |
| `xxl` | `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` | `x86_64`; Intel Xeon Platinum 8488C | `6.12.95-124.187.amzn2023.x86_64` | 192 |

Both archives report Rust and Cargo 1.93.1, LLVM 21.1.8, GCC 11.5.0, and
native flags `-C target-cpu=native -C debuginfo=1`. Timing used allowed CPU 0.
The raw records retain full target features, topology, affinity, tool versions,
binary hashes, and build environments.

The point estimate is minimal DAFSA elapsed time divided by flat-trie elapsed
time. `SD(log ratio)` is the sample standard deviation of the 12 complete-block
log contrasts in that host's run window.

| Host | Data set | DAFSA/trie ratio | Complete blocks | SD(log ratio) |
| --- | --- | ---: | ---: | ---: |
| Arm literal | `shared` | 0.639881 | 12 | 0.005819 |
| Arm literal | `opaque` | 1.033456 | 12 | 0.004840 |
| `xxl` | `shared` | 0.609596 | 12 | 0.002116 |
| `xxl` | `opaque` | 1.021655 | 12 | 0.003215 |

The same-method A/A ratios were 0.996292 and 0.999500 on Arm, then 0.999483
and 0.999315 on `xxl`, for `shared` and `opaque` respectively. Each uses four
complete blocks and remains separate from the treatment estimates.

The topology is host-independent because it is determined by the fixed input:

- `shared`: trie 790,801 states, 790,800 arcs, 12,652,808 topology bytes;
  DAFSA 16 states, 75 arcs, 728 topology bytes;
- `opaque`: trie 959,061 states, 959,060 arcs, 15,344,968 topology bytes;
  DAFSA 804,065 states, 869,599 arcs, 13,389,312 topology bytes.

On both hosts, compression helped elapsed lookup time for the highly shared
data and hurt it slightly for the opaque data. The exact ratios differ between
these two machines. That observation does not rank Arm against x86 or predict
another processor. The linked Arm loop contains `ldrh`, `ldrb`, `cmp`,
`b.cc`, `b.hi`, and `ldr`; the linked x86-64 loop contains `movzwl`, `movzbl`,
`cmp`, `jb`, `jbe`, and a target load. These are observed instructions, not a
cache or branch-cause diagnosis.

Both remote runners reported `CHECK=PASS`. After retrieval, the outer archive
digests, every inner manifest entry, and both independent receipt-validation
runs passed. See [`raw/7c9a4c3/SHA256SUMS`](raw/7c9a4c3/SHA256SUMS).
