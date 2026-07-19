# Measurement records

Each dated host record identifies the exact source candidate, resolved host,
kernel, CPU model, toolchain, native target flags, input, process count, timing
boundary, generated code, and raw-log checksum.

The comparison uses 12 fresh, paired, order-balanced processes per host. Each
process constructs both indexes over the same `2^26`-bit deterministic input,
warms both variants, and times 4,000,000 identical random positions. The
summarizer rejects missing pairs, order errors, duplicate process IDs, checksum
mismatches, or inconsistent byte counts.

Cross-host notes compare observations. They do not treat two guest machines as
samples of an instruction set, CPU vendor, kernel, or bare-metal platform.

Recorded evidence is added only after both required hosts complete the exact
source candidate.
