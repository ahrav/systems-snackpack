# x86-64 host record

## Boundary

- Host: `dev-dsk-ahrav-2c-b89a08b3.us-west-2.amazon.com`
- Window: 2026-07-17 15:13:45–15:13:53 UTC
- Source: commit `26b49a55473a8fc43b73d6e5e4ef58a7d72f3698`
- Archive SHA-256: `ba4a0704a4431c22714fdaa6111c144dcfa8da9a7cae246fce0a077a5ecaf217`
- CPU evidence: x86-64 AMD EPYC 9R14, family 25 model 17 stepping 1 under KVM; 48 CPUs available; process pinned to CPU 0
- Kernel: `6.12.94-123.180.amzn2023.x86_64`
- Toolchain: rustc 1.93.1, Cargo 1.93.1, LLVM 21.1.8, GCC 11.5.0
- Build flags: `-C target-cpu=native -C debuginfo=1 -C no-vectorize-loops -C no-vectorize-slp`

The [host probe](raw/26b49a5/dev-dsk-ahrav-2c/host-probe.txt) retains uname,
the CPU model fields, target features, compiler versions, affinity, and the
available CPU count.

## Workload

Each timed process scanned 262,144 fixed conditions 384 times after 16 warmup
scans: 100,663,296 decisions. The random stream contained 131,202 nonzero
conditions. Twelve fresh branch/select process pairs ran for each pattern. The
schedule crossed all six pattern orders with both variant orders.

Branch/select ratios above one favor select. The interval is the exact 96.1%
paired-median order-statistic interval under independent, identically
distributed continuous pair ratios.

| Pattern | Branch mean ± SD, ns/decision | Select mean ± SD | Paired geomean | Median ± MAD | Interval |
| --- | ---: | ---: | ---: | ---: | ---: |
| Zeros | 0.542506 ± 0.000260 | 0.393126 ± 0.000734 | 1.380 | 1.380 ± 0.001 | [1.379, 1.382] |
| Alternating | 0.425698 ± 0.014573 | 0.392916 ± 0.001012 | 1.083 | 1.077 ± 0.022 | [1.054, 1.118] |
| Random | 3.300727 ± 0.001554 | 0.392818 ± 0.000804 | 8.403 | 8.395 ± 0.008 | [8.392, 8.413] |

The point estimates and dispersion cover 12 paired process runs in this host
window. They do not cover new inputs, builds, hosts, or fleet variation.

## Timing and code generation

`timed_ns` excludes input construction, correctness checks, warmup, process
launch, and output. Across the six pattern/variant cells, median
`external_wall_ns - main_ns` was 3.65–3.88 ms. That difference includes process
launch, output capture, and shutdown; it is not a pure startup measurement.

The linked inner branch was `movzbl; mov 3; test; je; mov 7; add`. The select
was `movzbl; mov 3; test; cmovne; add`. Loop branches remained in both
functions. This is observed code generation, not a claim about other compilers
or x86 CPUs.

The random branch slowdown is consistent with wrong-path recovery. That
mechanism is inferred: this run did not collect a site-attributed miss rate.

## Validation and raw data

The equivalence example and benchmark verification passed. Formatting, unit
and example tests, doctests, Clippy with warnings denied, bench compilation,
and rustdoc with warnings denied passed under Rust 1.93.1. See the [raw host
directory](raw/26b49a5/dev-dsk-ahrav-2c/), including [all 72 process
records](raw/26b49a5/dev-dsk-ahrav-2c/benchmark/processes.txt), the [summary](raw/26b49a5/dev-dsk-ahrav-2c/benchmark/summary.txt), and [linked code](raw/26b49a5/dev-dsk-ahrav-2c/linked-focus.txt).
