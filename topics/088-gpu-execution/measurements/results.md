# Topic 088 evidence

2026-10-25. Final executable source commit: `7521bbd7bc7b071b5374db5f86de25a7a2fce2e8`.
The results commit changes only evidence. Source hashes are in `source.json`.
Both Linux hosts verified the same Git archive SHA-256 before compiling. Detailed
commands, architectures, toolchains, hashes, and output are retained per host.

| Host | Platform | Rust | Result |
| --- | --- | --- | --- |
| Local | Darwin arm64 | 1.99.0 | All six workspace gates pass; Python oracle passes |
| dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com | Linux aarch64 | 1.98.1 | Six Rust tests, one doctest, model output, Python oracle pass |
| xxl, resolved as dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com | Linux x86_64 | 1.99.0 | Six Rust tests, one doctest, model output, Python oracle pass |

The Rust suite checks 13,068 transpose results and 11,200 sector cases per host.
The separate Python model checks 8,712 transpose results per host. Linux compiles
use edition 2024 and warnings as errors; the printed model is optimized with
`-O`. These runs measure correctness only.

Local workspace gates passed formatting, Clippy with warnings denied, unit/bin/
example tests, doctests, benchmark compilation, and rustdoc with warnings denied.
The topic has no external dependencies. The rendered diagram was visually
inspected before the lesson was taught and before repository edits.

## Mechanism comparisons and limits

For a full aligned warp of four-byte values, aligned contiguous addresses touch
four sectors; a one-word shift touches five; a 1024-word stride touches 32.
At matrix width 1024, both tiled transpose alternatives reduce output sector
count from 32 to four per warp instruction. Padding changes the shared-column
bank depth from 32 to one while increasing block shared storage by 128 bytes.
The direct alternative uses zero shared storage and no block barrier.
These are deterministic model comparisons, not elapsed-time measurements.

Both declared hosts were reachable. Initial PATH probes and one bounded follow-up
checked standard CUDA paths and the NVIDIA device interface. `nvcc`,
`nvidia-smi`, `/usr/local/cuda/bin/nvcc`, `/opt/cuda/bin/nvcc`, and
`/dev/nvidiactl` were absent in the final probes. Local Darwin has no `nvcc`.

CUDA compilation, generated code, Compute Sanitizer checks, GPU timing samples,
variability, and workload-specific performance winners remain unmeasured. The
CUDA source is a candidate requiring device validation. CPU model success cannot
establish GPU execution correctness or speed. No timing winner is claimed.

## Pending device run

On a supported CUDA host, compile this exact source with the README commands,
run the independent-oracle checks and sanitizers, then run the nine-sample
rotated comparison of direct, tiled32, and tiled33. Preserve raw results, device
and toolchain metadata, clocks, cache regime, concurrent load, resource reports,
and per-shape min/median/max. Compare complete caller cost separately. This
missing device run does not block the next daily topic.
