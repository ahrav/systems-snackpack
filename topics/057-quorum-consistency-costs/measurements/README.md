# Correctness evidence, 2026-09-06

## Frozen identity

- Source commit: `4e006d61e733c3f2c011d8343ee25351f6b1d085`.
- Path-limited archive SHA-256: `88bf2c81f61b8b7b5339504634918ca1dd30443338329f0355b3594051986a55`.
- Exact runner SHA-256: `b7361b10e892fa5b8e470ff187deab568655046736fc14a4300dea8089ffbfd2`.
- Scope: root Cargo.toml/Cargo.lock and this topic only. Remote archive hashes
  matched; the transferred runner matched the archived runner byte for byte.
- The runner reads the commit ID that `git archive` stores in the tar's pax
  global header and refuses to run unless it equals the supplied source commit,
  so `source.txt` cannot name a commit the digest-verified archive does not
  contain. A deliberate mismatch run on the x86 host exited 1 before writing
  any receipt.
- Rust source bytes (`src/lib.rs`, `examples/quorum.rs`) are identical to the
  first tested commit `8754251dfb00b8af11e2ede2e6b33b4d482a5ada`; only the
  runner and receipts changed between the two runs. Both hosts' `library.s`
  and `quorum` example binaries hash identically across the two runs; only the
  rlib metadata (both hosts) and the x86 test binary differ.

## Hosts and results

| Property | Required Arm host | Runtime-resolved xxl |
|---|---|---|
| Hostname | dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com | dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com |
| Architecture | aarch64 | x86_64 |
| CPU identity | ARM implementer 0x41, part 0xd40, revision 1 | Intel Xeon Platinum 8488C |
| Available CPUs (nproc) | 64 | 192 |
| Kernel | 6.12.103-127.188.amzn2023.aarch64 | 6.12.95-124.187.amzn2023.x86_64 |
| rustc | 1.95.0, 59807616e | 1.98.0, 88d9e12ae |
| Topic unit tests | 9 passed | 9 passed |
| Topic doctest | 1 passed | 1 passed |
| Example | inversion 1 then 0; write-back 9/9 | inversion 1 then 0; write-back 9/9 |

Commands are implemented by `experiment/run_host.sh`. Builds use
`--edition=2024 -C opt-level=2 -D warnings` with default target features. Full
compiler identity, CPU data, kernel, and `rustc --print cfg` are in host.txt.

The standalone initial example also passed on both hosts before repository edits.
The final workload includes overlap for all read/write sizes through N=7 and
305,206 query/write-back/later-read combinations over single-site exposure states
for N=3,5,7. Some queries intentionally observe zero; those are controls.

## Generated code

The non-inlined `retain_tag` appears in the emitted library and linked example.
Arm uses `cmp x1, x0; csel x0, x1, x0, hi; ret`. This x86 build uses
`mov %rdi,%rax; cmp %rdi,%rsi; cmova %rsi,%rax; ret`.
These are observations of two exact builds. They neither prove the distributed
protocol nor support an architecture-wide performance comparison.

## Validation and evidence boundary

All required local workspace gates passed on rustc 1.93.1, aarch64-apple-darwin:
diff hygiene, formatting, 307 library/example tests, 118 doctests, Clippy with
warnings denied, benchmark compilation, and rustdoc with warnings denied.
Bash syntax and ShellCheck passed. Complete code and prose review found no
remaining mismatch between stated finite coverage and implementation.

No network/storage latency, throughput, failure probability, or hardware timing
was measured. The printed 4.2 ms phase and 8.4 ms two-phase costs are hypothetical
input calculations. Test-runner elapsed times are not replication measurements.
The workload omits real persistence, failures, restarts, changing membership,
and arbitrary concurrent histories.

Compact raw text and SHA256SUMS are included here. Full sealed receipts, exact
source archive, runner, native assembly, linked disassembly, binaries, initial
logs and local gate logs are retained in the curriculum evidence directory for
Topic 57. The full receipt includes hashes of large replay assets omitted from
this compact repository artifact.

Repository test-log copies trim trailing blank lines for diff hygiene. Their
SHA256SUMS cover those copies; retained sealed originals remain unchanged.
