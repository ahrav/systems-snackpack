# Exact-source correctness evidence

Source commit: `a2c902dd8fd9e8b44d8c3ece6af6d1add15b6290`.
Archive SHA-256: `aa20a831d1a611685ff1789504185cd4f171636c707376172237774c1c88285d`.
Runner SHA-256: `0519ac664ba7b4249e815d025655d4a8e2fc4b9d853efeb92a27a0bc3a9ea4fa`.
Execution: 2026-09-27 UTC. These text copies normalize leading/trailing blank
lines; original sealed receipts and binaries are retained at
`/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-059/2026-09-27-a2c902dd`.

Both required hosts passed seven tests, one doctest and the deterministic example.
The snapshot test makes 13,776 read-equivalence comparisons over eight histories,
41 floor values, all modeled subsequent reads, and two outside-version states.
The unsafe control confirms that deleting a necessary tombstone resurrects data.
The comparison count describes a finite modeled domain, not exhaustive engine verification.

- Arm: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, aarch64, 64 available CPUs,
  CPU implementer 0x41 / part 0xd40 / r1p1, Linux 6.12.103-129.197.amzn2023.aarch64,
  rustc 1.98.1, LLVM 22.1.8. The host reports a numeric CPU identity; no vendor-family
  performance conclusion is inferred.
- xxl resolved at runtime to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com,
  verified x86_64, 192 available CPUs, Intel Xeon Platinum 8488C,
  Linux 6.12.103-127.188.amzn2023.x86_64, rustc 1.98.0, LLVM 22.1.8.

Both used edition 2024, opt-level=2, generic target CPU, and no LTO. Full target
features, toolchain commits, uname, lscpu, and CPU-count records are in host.txt.
Native debt calculation uses low/high multiply and carry handling on Arm, and
mulq/addq/adcq on x86, followed by saturating subtraction and a high-half check.
This inspection establishes emitted arithmetic, not instruction throughput.

Expected and observed output on both hosts:

```text
pinned=3 guarded=1 reclaimed=0
transfer_mib=608 debt_mib=420
```

Each runner verified its host/architecture, archive digest and embedded commit,
path-limited members, and equality with its committed copy before compilation.
Each retrieved receipt archive and ten constituent files passed SHA-256 validation.
The initial scratch example also passed on both hosts before worktree creation.

No benchmark comparison was made. Wall-clock durations printed by the test
framework are not performance samples. This model has no storage I/O and cannot
estimate engine throughput, physical write amplification, or architecture effects.
The 1.52-second transfer bound and 30-/20-second debt calculations are illustrative
inferences from assumed rates, not measured facts.

Local workspace formatting, library/example tests, doctests, Clippy with warnings
denied, benchmark builds, and rustdoc with warnings denied all passed. Shell syntax
and ShellCheck passed for the runner. Root Cargo.lock changed only to add this crate.
