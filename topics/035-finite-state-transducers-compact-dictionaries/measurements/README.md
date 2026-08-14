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

No exact-source result has been promoted yet.
