# Exact-source evidence, 2026-09-28

Source commit: `09bdf7aca886f3e18e8e438cb7e3c4a5620921bf`.
The later measurement-only commit leaves the tested source and runner unchanged.
Full logs, assembly, replay archive, initial controls, and checksums are retained
outside Git. See [receipt](EVIDENCE_RECEIPT.json).

| Host | CPU and available CPUs | Kernel | Compiler |
|---|---|---|---|
| dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com | aarch64, implementer 0x41, part 0xd40, revision 1; 64 | 6.12.103-129.197.amzn2023.aarch64 | rustc 1.98.1, LLVM 22.1.8 |
| xxl resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com | x86_64, Intel Xeon Platinum 8488C; 192 | 6.12.103-127.188.amzn2023.x86_64 | rustc 1.98.0, LLVM 22.1.8 |

Cargo release opt-level=3, default target CPU, RUSTFLAGS and encoded flags unset.
Compiler default features include neon on Arm and fxsr/sse/sse2 on x86.
Full uname, CPU flags, toolchain identities, and target cfg are in the receipts.

Both initial scratch runs reproduced the unsafe deletion, duplicate merge, and
negative underlying count controls before repository mutation. Both final runs
verified the exact path-limited source archive and runner SHA-256 values before
execution. Ten tests and one doctest passed on each host.

## Observed results

One example process per host, each enumerating the same 16 deterministic seeds.
Each seed queries 100,000 known-absent keys per insertion population. The two
hosts produced identical counts; they are reproducibility checks, not 32 distinct
seed samples. These mixer seeds are not proved independent random trials.

| Distinct inserted keys | Bits / probes | Median false-positive rate | Seed minimum to maximum |
|---|---|---|---|
| 10,000 | 95,851 / 7 | 1.017% | 0.972% to 1.055% |
| 20,000 | 95,851 / 7 | 15.719% | 15.469% to 16.052% |

All inserted keys remained present. The same absent-query domain is disjoint
from both inserted sets. Per-seed outputs are retained. These descriptive ranges
are not confidence intervals or proof of the textbook approximation.

Count-Min matched a serial exact-stream build after merging disjoint event
partitions. Exact input total was 3,997; all 1,000 key estimates were at least
their exact count. Largest observed additive error was 16. Replaying the odd-key
partition produced total 5,997, correctly exposing duplicate aggregation.

No timing is reported. Runtime cannot decide these semantic contracts, and a
production hash or cache-layout comparison would require a separate experiment.
The service-cost arithmetic in the README remains illustrative.

## Generated code and local validation

Inspected both non-inlined query functions. Arm uses multiply/xor mixing,
unsigned division/remainder, indexed loads and a bit-test loop for Bloom;
Count-Min uses a conditional-select minimum. x86 uses integer multiply/xor,
unsigned division, indexed loads and a bit test; Count-Min uses conditional move.
Bounds checks remain. This confirms compiled paths, not optimality or randomness.

All seven local gates passed: diff check, formatting, workspace library/example
tests, workspace doctests, Clippy with warnings denied, benchmark compilation,
and rustdoc with warnings denied. The final test-only lint corrections also
passed the focused tests; no unrelated source or lockfile change is published.

Replay from the retained archive root:

```sh
sha256sum topic61-source.tar topic61-runner.sh
# Compare both values with EVIDENCE_RECEIPT.json before extraction.
tar -xf topic61-source.tar
sh topic61-runner.sh
```

The runner executes tests, the example, and optimized assembly generation. The
archive contains only workspace metadata and this topic. No external crate or
network access is required for the two-host replay.
