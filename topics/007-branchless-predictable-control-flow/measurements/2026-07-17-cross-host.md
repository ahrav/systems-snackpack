# Cross-host comparison

Both hosts ran the same pushed commit and archive with the same Rust toolchain,
flags, input bytes, repetitions, warmup, pair count, and balanced schedule.
They are two host observations, not representative samples of their ISAs or
vendors.

Branch/select ratios above one favor select.

| Host | Architecture evidence | Zeros | Alternating | Random |
| --- | --- | ---: | ---: | ---: |
| `2b` | Arm `0x41/0xd40`, AArch64 | 1.066 | 1.240 | 4.846 |
| `2c` | AMD EPYC 9R14, x86-64, KVM | 1.380 | 1.083 | 8.403 |

The table reports paired geometric means from 12 fresh process pairs per cell.
Host records contain SD, median, MAD, and exact 96.1% paired-median intervals.
The interval model assumes independent, identically distributed continuous
pair ratios and covers only process variation in each run window.

Measured differences:

- Select timing changed little across outcome patterns within either host.
- Random branch timing was 4.846 times select on `2b` and 8.403 times select on
  `2c`.
- Alternating branch results were more dispersed than the zeros or select
  results, especially on `2b`.
- Process-boundary overhead was recorded separately from the timed kernel.

Observed linked code retained the intended decision shapes: `cbz` versus
`cmp/csel` on `2b`, and `test/je` versus `test/cmovne` on `2c`. Both binaries
also retained their loop branches.

The timing alone does not measure branch misses or recovery latency. Predictor
behavior is a plausible mechanism, not a measured cause. Clock rate,
microarchitecture, virtualization, code placement, and other host differences
also differ, so the ratio gap must not be attributed to ISA alone.

See the [AArch64 record](2026-07-17-dev-dsk-ahrav-2b.md), [x86-64
record](2026-07-17-dev-dsk-ahrav-2c.md), and [raw evidence](raw/26b49a5/).
