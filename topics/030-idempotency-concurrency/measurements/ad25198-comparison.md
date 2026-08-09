# Two-host correctness comparison: `ad25198`

Both required Linux targets ran the same source commit and source archive.
This is historical evidence for commit
`ad2519824f2e309a287c9b7dc957bdd80eec86c9`; it does not attest later branch
commits or the eventual merge or squash commit. The `xxl` alias resolved at run
time to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` and reported `x86_64`. The
literal Arm target reported `aarch64`.

## Shared result

- Source commit: `ad2519824f2e309a287c9b7dc957bdd80eec86c9`
- Source archive SHA-256:
  `a300f6126e3fb912ed39db029ef3a70cc22639b0d6bab5408398525c41ae614a`
- Source-manifest file SHA-256:
  `d8ee37bc57cca73c2720e346b8714cda89c76d184db019d62447c5656c5d4a86`
- Expected-output SHA-256:
  `c02b0b49223077d9100985e95c069e452ecb97fe533b0a114da77b13541e4879`
- Replication: eight generic and eight native fresh processes per host; 32 of
  32 passed with empty standard error
- Independent receipt validation, source stability, and every workspace gate:
  PASS on both hosts

## Host-specific observations

| Target | Architecture and CPU | Kernel | Final native code |
| --- | --- | --- | --- |
| Literal Arm host | `aarch64`; 64 CPUs; Arm `0x41:0xd40`, r1p1 | `6.12.95-124.187.amzn2023.aarch64` | conditional branches plus `cinc`, `csel`, `ccmp`, and `cset` |
| `xxl` alias | `x86_64`; 192 CPUs; Intel Xeon Platinum 8488C under KVM | `6.12.94-123.180.amzn2023.x86_64` | conditional branches plus `sete`, arithmetic, and `and` |

LLVM 21.1.8 emitted different sequences for the two instruction set
architectures. Both implement the same tested return-value contract. The
receipts also record different native feature sets, but these two hooks contain
no identified native-only instruction. This is observed code generation, not
evidence that one host or architecture is faster.

## Why there is no timing interval

The experiment tests a process-local model whose lock stands in for a durable
transaction. It omits log flushes, database conflicts, network delay, external
effects, recovery, and retention. A timing interval would describe simulator
startup and lock scheduling, not the cost of a production idempotency design.

The two-host evidence therefore supports only correctness portability for the
retained source, compilers, binaries, hosts, and run windows. Production crash
behavior and remote-effect safety remain inferred design requirements.
