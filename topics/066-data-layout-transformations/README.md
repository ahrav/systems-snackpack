# Data layout transformations

Equivalent eight-field AoS, SoA and 16-lane AoSoA implementations. Logical row
identity, bounds, wrapping arithmetic and tile tails remain invariant.

Run `cargo test -p data-layout-transformations` and
`python3 topics/066-data-layout-transformations/scripts/run.py /tmp/topic066-results`.
The output directory must not exist. Python 3.9+ and Rust 1.93+ are required.

The runner records exact inputs, host/toolchain, generated assembly, correctness,
486 balanced processes, dispersion and the predeclared selection rule.
See [experiment controls](EXPERIMENT.md), [round notes](rounds/01.md), and
[measurement status](measurements/README.md).
