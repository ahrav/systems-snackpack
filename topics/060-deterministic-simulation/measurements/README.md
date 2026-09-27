# Two-host correctness evidence, 2026-09-27

Source commit: `5560b4aa1b921f2701e3816a7de83f8efec76bec`.
The follow-up evidence commit changes only this directory. The frozen archive
contains root Cargo.toml/Cargo.lock and this topic. The extracted workspace has
only this member. Cargo can prune unrelated lock entries; tested source is unchanged.

| Host | Architecture and CPU | Kernel | Toolchain | Available CPUs |
| --- | --- | --- | --- | --- |
| dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com | aarch64; ARM implementer 0x41, part 0xd40, variant 1, revision 1 | 6.12.103-129.197.amzn2023.aarch64 | rustc 1.98.1, LLVM 22.1.8 | 64 |
| xxl, resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com | x86_64; Intel Xeon Platinum 8488C | 6.12.103-127.188.amzn2023.x86_64 | rustc 1.98.0, LLVM 22.1.8 | 192 |

Both the ephemeral initial example and exact committed-source run passed on both
hosts. The final run passed eight unit tests, one doctest, and the example.
Source/archive/runner and all six sealed evidence files per host passed SHA-256
verification. Complete uname, CPU flags, compiler identity, output, and assembly
are retained externally in the receipt's named checkpoint.

| Model and bound | Terminal schedules | Failures | Edges | Cutoffs | Status |
| --- | --- | --- | --- | --- | --- |
| Split, depth 4 | 6 | 4 | 18 | 0 | Exhausted |
| Atomic, depth 2 | 2 | 0 | 4 | 0 | Exhausted |
| Split, depth 3 | 0 | 0 | 12 | 6 | Cutoff |

Both hosts replayed `[0, 1, 0, 1]` to value 1 with two completed workers.
These are exact model counts, not estimates or performance samples. Process
replication, timing dispersion, and order balancing are not useful for this
correctness-only question. Native assembly retains recursive search calls:
AArch64 `bl ...search5visit`; x86-64 `callq ...search5visit`. This establishes a
compiled search path, not hardware atomicity or a proof that a service refines
this model.

## Reproduce the final run

From the repository, freeze the tested source:

```sh
git archive --format=tar 5560b4aa1b921f2701e3816a7de83f8efec76bec \
  Cargo.toml Cargo.lock topics/060-deterministic-simulation > topic60-source.tar
mkdir topic60-replay
cd topic60-replay
tar -xf ../topic60-source.tar
sh topics/060-deterministic-simulation/scripts/run-linux.sh
```

Use Linux with the recorded Rust toolchain. The runner unsets RUSTFLAGS and
CARGO_ENCODED_RUSTFLAGS, uses Cargo's default target CPU and release optimization
level 3, and saves the exact commands' output. No target-native flag is used.

All seven required local workspace gates passed with Rust 1.93.1 on macOS:
diff check, formatting, library/example tests, doctests, strict Clippy, benchmark
compilation, and warning-free rustdoc. An initial example missing-docs error was
fixed before source commit. Root Cargo.lock adds only this dependency-free crate.
Shell syntax checking and an independent six-permutation enumeration also passed.

Sourced tool distinctions are linked in the topic README. The counts above are
measured executions of this model. Any application to production correctness is
an inference requiring a separately justified model-to-implementation mapping.
