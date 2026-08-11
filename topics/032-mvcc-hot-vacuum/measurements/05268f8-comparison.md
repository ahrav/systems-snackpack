# Two-host comparison: `05268f8`

Both required Linux targets ran the same pushed source commit and source
archive. Each host produced eight generic-build and eight native-build
fresh-process receipts. This is a correctness and generated-code comparison,
not a timing benchmark.

| Retained observation | Required Arm | Runtime-resolved `xxl` |
| --- | --- | --- |
| SSH target | literal host | alias resolved to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` |
| Architecture | `aarch64` | `x86_64` |
| Platform product | `c7g.16xlarge` | `c7i.48xlarge` |
| CPU identity | Arm model `1`, stepping `r1p1`, MIDR `0x411fd401` | Intel Xeon Platinum 8488C, family 6/model 143/stepping 8 |
| Available CPUs | `64` | `192` |
| rustc / LLVM | `1.93.1` / `21.1.8` | `1.93.1` / `21.1.8` |
| Generic process passes | `8/8` | `8/8` |
| Native process passes | `8/8` | `8/8` |
| Generic binary SHA-256 prefix | `1fbfd435` | `95b269b3` |
| Native binary SHA-256 prefix | `556be5f1` | `6ab3c298` |
| Snapshot-bound selector | conditional selects, no branch | one early conditional branch plus set-byte operations |
| Reclamation predicate | `cmp`, `cset` | `cmp`, `setb` |

Every process on both hosts produced the same expected-output digest. Both
hosts retained both inspection symbols and passed the same source-stability and
workspace gates. The different binary hashes and instructions are observations
of these compiler, target-feature, and host combinations. They are not an Arm
versus x86 performance comparison.

No per-execution latency, performance dispersion, or confidence interval is
reported. The experiment tests deterministic visibility, update-chain,
index-entry, and reclamation state transitions. The recorded host-run windows
are evidence timestamps, not benchmark samples. Timing this small model would
not estimate PostgreSQL lock, storage, write-ahead-log, cache, concurrency, or
background-maintenance cost.

Evidence:

- [Arm record](05268f8-arm.md)
- [`xxl` record](05268f8-xxl.md)
- [Outer archive hashes](raw/05268f8/SHA256SUMS)
