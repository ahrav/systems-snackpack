# Measurement contract

The checked-in record applies only to its named source commit, linked binary,
hosts, compilers, flags, inputs, and run window.

Each comparison contains 12 fresh-process pairs. Pair order alternates `AB` and
`BA`; `A` is the candidate (`imported` or `opaque`) and `B` is `local`. The
estimate is the geometric mean of the candidate/local ratio across pairs. A
fixed-seed bootstrap resamples pair log-ratios and reports its 2.5th and 97.5th
percentiles. The interval covers observed process-to-process variation within
that run window. It does not cover independent builds, other hosts, or future
load.

One untimed warm-up occurs in every fresh process. `steady_ns` covers only the
round loop. `process_ns` also includes process launch, allocation, input
generation, correctness checks, warm-up, and output. Their difference is not a
calibrated pure-startup measurement.

For code generation, retain the final linked disassembly, symbol table, binary
digest, native target features, and build flags. Interpret elapsed time only
after confirming that the visible and opaque variants compiled differently.
