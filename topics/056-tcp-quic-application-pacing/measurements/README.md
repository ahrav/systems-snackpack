# Exact-source correctness campaign

Source commit: `b2473a3d231f3504b483ce0b33e60b9d28b61f90`.
The path-limited archive and byte-identical runner hashes appear in both identity
records. Every archived source file was independently compared with its Git
blob, and every retained receipt member passed SHA-256 verification. Before
and after source manifests match. Each sealed receipt contains 11 data files.

| Host | Correctness | No-pause overdue/capped burst | Paused overdue/capped burst |
| --- | --- | --- | --- |
| Arm, 64 online CPUs, lscpu Vendor ARM / Model 1 | 7 tests passed | 1 / 2 chunks | 51 / 2 chunks |
| xxl, x86-64, Xeon Platinum 8488C, 192 online CPUs | 7 tests passed | 1 / 2 chunks | 51 / 2 chunks |

The xxl alias resolved at runtime to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` and returned `x86_64`.
Arm host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`.
Kernel, toolchain, available CPU counts, and default build features are in the
host records. The Arm model is identified from the committed host record's lscpu output
(Vendor ID ARM, Model 1, Stepping r1p1);
no processor marketing name is inferred.

Compact test logs trim surrounding blank lines; full logs remain in the sealed
receipts.

Both examples admitted all 100 chunks and checked every contiguous interval
against the capped byte envelope. Simulated completion times were 9,900/9,800
microseconds without the pause and 9,900/14,700 with it, overdue/capped.
Each host ran one deterministic correctness campaign; there is no performance
sample, dispersion estimate, ISA comparison, or transport throughput claim.

Generated-code review found retained refill arithmetic and capacity comparisons
in both target examples. The reviewed Arm code uses `cmp`/`csel`; the x86 code
uses `cmp`/`cmovae`. This confirms the inspected code shape, not instruction
cost or departure timing. Full assembly, disassembly, binaries, host metadata,
and receipt archives remain at the locator in `retained.txt`.

## Replay

From the repository, create the source archive at the recorded source commit:

```bash
git archive --format=tar.gz --output=source.tar.gz \
  b2473a3d231f3504b483ce0b33e60b9d28b61f90 \
  topics/056-tcp-quic-application-pacing
git show b2473a3d231f3504b483ce0b33e60b9d28b61f90:topics/056-tcp-quic-application-pacing/experiment/run_host.sh > run_host.sh
```

In fresh Linux scratch containing only these two files, first verify the runner
against the identity record. Use `aarch64` on Arm and `x86_64` on xxl:

```bash
sha256sum source.tar.gz run_host.sh
bash run_host.sh aarch64 \
  bb1a91a03b2b4a55863023982cd553988bc959b8ff2d3c4a46c767cdcf3e5432 \
  88dd527034c211697f6ef4eb8b4c8d62762be9fb25d72e7050e2681559b5d7b1 \
  b2473a3d231f3504b483ce0b33e60b9d28b61f90
```

`local-gates.json` records successful workspace library/example tests,
doctests, Clippy with warnings denied, benchmark compilation, and rustdoc with
warnings denied. Formatting, diff whitespace, Bash syntax, ShellCheck, and a
focused rustdoc rerun after prose clarification also passed. Source code and
runner remain byte-identical to the measured commit; this later commit adds
only compact evidence records.
