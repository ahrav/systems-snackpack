# Exact-source correctness evidence: 2026-09-30

Source commit: `ef04a46f77bcfa517ea42e87aa16d26c5375fd07`. The evidence commit adds prose only.
Later review-fix commits change tested source and runner: `repair_read` and
`receive` keep a key with no retained history absent (one new unit test), the
example asserts the repaired key converged, the runner pins `CARGO_TARGET_DIR`,
resets it before codegen, requires exactly one assembly candidate, and records
effective rustc flags and Cargo environment, and `scripts/test-run-linux.sh`
exercises those runner properties. The recorded hosts ran the source commit.
Source archive SHA-256: `da99f2846d82009a765bf8a85539146dc24b2db4fe9b5a599e052d4f518c3175`.
Runner SHA-256 at the time of this run: `c9902748a3f99bb8412a69f64691dba195ebb5070d02d353e6147a7049340aab`.
Archive scope, transfer hashes, source files, and retrieved inner receipt hashes
were verified locally. The archived Rust source and runner match the source commit.

| Host | Hardware and kernel | Toolchain | Result |
|---|---|---|---|
| `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | aarch64; CPU implementer 0x41, part 0xd40, variant 1, revision 1; 64 available CPUs; Linux 6.12.103-129.197.amzn2023.aarch64 | rustc 1.98.1, LLVM 22.1.8 | 11 unit tests, one doctest, example, code generation passed |
| `xxl`, resolved to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` | x86_64; Intel Xeon Platinum 8488C; 192 available CPUs; Linux 6.12.103-127.188.amzn2023.x86_64 | rustc 1.98.0, LLVM 22.1.8 | 11 unit tests, one doctest, example, code generation passed |

Cargo default release optimization level three, default target CPU, RUSTFLAGS
and CARGO_ENCODED_RUSTFLAGS unset. Receipts retain hostname, uname, CPU data,
compiler and Cargo versions, and target feature configuration. The current
runner also unsets `CARGO_BUILD_RUSTFLAGS` and `CARGO_BUILD_TARGET`, pins
`CARGO_TARGET_DIR` to `./target`, empties it before the codegen step so every
run rebuilds and yields exactly one assembly file, and writes the effective
`rustc` invocation to `codegen.txt` and any `CARGO_*` environment to `host.txt`.

Both hosts observed three converged replicas retaining two concurrent siblings.
Retaining the delete blocked the old value; forgetting it resurrected the value.
Read repair left the cold key stale; delivering the repaired replica's full
catalog with `receive` repaired it. One changed
record selected one four-record range in the exact sixteen-record range oracle.
These are deterministic model observations, not database or network results.

The finite law checks cover 32 normalized fixture subsets (some normalize to
the same state), 1,024 pairs, and 32,768 triples. Passing these does not prove
unbounded convergence, fair delivery, durable counters, or safe garbage collection.
No benchmark timing was used because tiny container operations do not measure
repair throughput. No random-gossip or hardware-family comparison is claimed.

Both native `before` functions retain unsigned componentwise comparisons and
strict inequality. Arm uses `cmp`/`b.ls`, then `ccmp`/`cset`; x86-64 uses
`cmpq`/`jbe`, then packed equality and `setne`. This validates code shape only.

All seven required local gates passed with repository-pinned Rust 1.93.1:
diff, formatting, workspace library/example tests, doctests, warning-free Clippy,
benchmark compilation, and warning-free rustdoc.

Sealed raw evidence and replay inputs are outside Git:
`/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-063/2026-09-30-ef04a46f` (55 files).
They include source archive, exact runner, initial scratch runs, both host
receipts, assembly, local gate logs, and a SHA-256 manifest.

Replay in a Linux scratch workspace containing the archived root manifest,
lockfile, and this topic: `sh topics/063-anti-entropy/scripts/run-linux.sh`.
The runner clears and rewrites `evidence/` and `target/` under the workspace on
every run. Do not commit `evidence/`. Run the runner's own checks from the
repository root with `sh topics/063-anti-entropy/scripts/test-run-linux.sh`.
