# Two-host comparison: `b9bb526`

Both required Linux targets ran the same pushed source commit and source archive.
Each host produced eight generic-build and eight native-build fresh-process
receipts. This is a correctness and generated-code comparison, not a timing
benchmark.

| Retained observation | Required Arm | Runtime-resolved `xxl` |
| --- | --- | --- |
| Architecture | `aarch64` | `x86_64` |
| Available CPUs | `64` | `192` |
| rustc / LLVM | `1.95.0` / `22.1.2` | `1.97.1` / `22.1.6` |
| Generic process passes | `8/8` | `8/8` |
| Native process passes | `8/8` | `8/8` |
| Generic binary SHA-256 prefix | `327ac12e` | `4ac8055f` |
| Native binary SHA-256 prefix | `41ed963d` | `c5bf8fe5` |
| Wall selector | `cmp`, `cset` | `cmp`, `seta` |
| Lamport receive | `cmp`, `csel`, `add` | `cmp`, `cmova`, `lea` |
| Vector relation | branches | branches |
| HLC receive | conditional selects and branches | conditional moves and branches |

Every process on both hosts produced the same expected-output digest. Both
hosts retained all four inspection symbols and passed the same source-stability
and workspace gates. The different binary hashes are expected because the
architectures, compiler versions, and native feature sets differ.

The instruction names describe the retained binaries only. They do not compare
Arm with x86, processor vendors, or fleet performance. No elapsed-time value,
dispersion, or interval is reported because the experiment tests deterministic
state transitions. Timing local comparisons would not estimate message,
metadata, persistence, uncertainty-wait, or agreement cost.

Evidence:

- [Arm record](b9bb526-arm.md)
- [`xxl` record](b9bb526-xxl.md)
- [Outer archive hashes](raw/b9bb526/SHA256SUMS)
