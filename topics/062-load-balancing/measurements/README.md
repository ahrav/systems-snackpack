# Exact-source correctness evidence: 2026-09-29

Source commit: `30fdab0b9b9ca46d5a757431f8b7b5d42e221490`. The evidence commit adds this
directory only. Later review-fix commits harden the runner (pinned `CARGO_TARGET_DIR`,
target reset before codegen, exactly one assembly candidate, effective rustc
flags and Cargo environment recorded) and add `scripts/test-run-linux.sh`; tested
Rust source is unchanged.
Source archive SHA-256: `152be30de1c8492af8764c0ccd14e4190a5558e2a18dc54776b492a3624babd6`.
Runner SHA-256 at the time of this run: `5989f0d060bfa6cff00b4a4358dc4325329948b7f5a579275b3daf9adf147b05`.
Both transfer identities and retrieved inner receipts were checked locally.

| Host | Hardware and kernel | Toolchain | Result |
|---|---|---|---|
| `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` | aarch64; CPU implementer 0x41, part 0xd40, variant 1, revision 1; 64 available CPUs; Linux 6.12.103-129.197.amzn2023.aarch64 | rustc 1.98.1, LLVM 22.1.8 | 10 tests, one doctest, example and code generation passed |
| `xxl`, resolved at runtime to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` | x86_64; Intel Xeon Platinum 8488C; 192 available CPUs; Linux 6.12.103-127.188.amzn2023.x86_64 | rustc 1.98.0, LLVM 22.1.8 | 10 tests, one doctest, example and code generation passed |

Cargo default release optimization level three; default target CPU; `RUSTFLAGS`,
`CARGO_ENCODED_RUSTFLAGS` and `CARGO_BUILD_TARGET` unset. Host receipts retain `uname -a`, CPU data,
`rustc -Vv`, Cargo version and `rustc --print cfg` target features. The current
runner pins `CARGO_TARGET_DIR` to `./target`, empties it before the codegen step so
every run rebuilds and yields exactly one assembly file, and writes the effective `rustc` invocation to
`codegen.txt` and any `CARGO_*` environment to `host.txt`, so a replay under
overrides or a reused target directory is visible.

Both hosts produced stale `[16,1,1,1]`, reserved `[5,5,5,4]`, and all-ordered-pair
`[7,4,4,4]` final counts. Batch drain times were ten and four model units for
equal and capacity-proportional assignments. These are model outputs, not
measured proxy latency, throughput, random-sample intervals or architecture speed.

Generated `two_choice` code retains candidate bounds checks on both hosts.
AArch64 uses two loads plus `csel`; x86-64 uses loads/comparison plus `cmovbq`.
Both choose the first candidate on ties. No timing conclusion follows.

All seven required local gates passed using the repository-pinned Rust 1.93.1:
diff check, formatting, workspace library/examples, doctests, warning-free Clippy,
benchmark compilation, and warning-free documentation. The initial missing
example crate doc was fixed before accepted validation.

Retained sealed replay evidence (ordinary local storage, outside Git):
`/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-062/2026-09-29-30fdab0b`.
It contains the path-limited source archive, exact runner, host receipts,
initial scratch runs, optimized assembly, gate logs and SHA-256 manifest.

To rerun in a Linux scratch workspace containing only the root manifest,
lockfile and this topic:

```bash
sh topics/062-load-balancing/scripts/run-linux.sh
```

The runner clears and rewrites `evidence/` on every run. Do not commit it.
Completion lifecycle and concurrent admission are deliberately not modeled.
