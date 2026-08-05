# Cross-host comparison

Both hosts executed commit `5f93fdb1472adaf23396ca9c19d0e327adfaab1a`
from archive SHA-256
`e024cea840cd416130ab08e2669a909c7046af2f854d8687f5f14a508805b368`.
These are two host observations, not claims about every AArch64 or x86 CPU.

Toolchain disclosure: the runner did not enforce the workspace's
`rust-toolchain.toml` pin at measurement time. The Arm host measured with
rustc 1.95.0 and the `xxl` host with rustc 1.93.1, as recorded in each
`host.txt`, so the cross-host contrast confounds architecture with compiler
version. The runner now fails closed on a pin mismatch for future runs.

Codegen provenance: the per-instruction observations below were read from the
run's `objdump` output of the measured binaries, which was produced by the
runner but not retained in `measurements/raw/5f93fdb`. The retained
`lowering-*.s` files come from separate `rustc --emit=asm` invocations of the
same source and toolchain, not from the measured binaries. The runner's
evidence manifest now seals the objdump output for future runs.

## Measured

- Release and Relaxed private-line store throughput was indistinguishable at
  this resolution on both hosts.
- Arm SeqCst and Release stores were also indistinguishable: ratio 0.999962,
  IQR 0.999380–1.003885.
- On `xxl`, the SeqCst/Release store ratio was 33.987073, IQR
  33.969202–34.011173.
- SeqCst and Relaxed private-line RMW throughput was within 0.13% on both hosts.
- Release/Acquire store buffering produced `r00` on both hosts in at least one
  native or generic build. SeqCst produced no `r00` in these bounded runs.

The interval is dispersion across 12 order-balanced process blocks. It is not
an uncertainty interval over inner-loop operations or a cross-machine
population interval.

## Observed code generation

- Arm native store Release and SeqCst both used `STLR`. Native Relaxed and
  SeqCst `fetch_add` used `LDADD` and `LDADDAL`; generic RMWs used outline
  helpers.
- `xxl` Release stores used `movq`, SeqCst stores used `xchgq`, and both RMW
  orderings used `lock xaddq`.
- The Arm native Acquire load used RCpc `LDAPR`; its generic counterpart used
  `LDAR`. Rust semantics did not change with the selected instruction.

## Inferred mechanism

The matching store instruction on Arm and differing `movq`/`xchgq` loop on
`xxl` explain the direction and scale of the private-line store contrast. This
is an evidence-supported inference, not an isolated causal experiment. The
measured 0.999307 and 1.001299 RMW ratios contradict a monotonic ordering-cost
rule for these binaries: ownership and the RMW instruction dominated the
ordering suffix. This experiment does not constrain contended cases, where
coherence queueing adds a separate term.
