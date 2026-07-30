# Measurements

Each host record names:

- runtime alias and resolved hostname;
- architecture, CPU evidence, kernel, selected CPU, sibling topology, and
  available CPU count;
- Rust toolchain, native build flags, source commit, source archive digest, and
  binary digest;
- node count, working-set bytes, useful loads, process count, order schedule,
  startup boundary, and run window;
- one- and eight-chain medians, paired point estimate, interval, dispersion, and
  A/A diagnostic;
- final-image code generation and PMU availability;
- measured facts, vendor evidence, and inferred mechanisms as separate claims.

Raw evidence lives below `raw/<source-prefix>/`. The cross-host note compares
exact runs without treating two hosts as instruction-set populations.
