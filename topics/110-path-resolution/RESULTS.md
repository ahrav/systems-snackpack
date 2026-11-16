# Topic 110 results

Exact tested source: `7afe438b6694e9bed2a1e72f194dad6842bd8ea6`.
Archive SHA256: `806c3e83e3bb45f6b55e5e38e6f58fa46403a6daa1f1edf18c10e98205da3531`.
Both Linux transfers passed SHA256 verification before extraction and execution.
All executable input bytes remain unchanged in the published commit.

## Observed correctness

Local macOS arm64 and both Linux hosts passed three Rust unit tests, one doctest,
and the Python deterministic check/use reproducer. The reproduced ordinary open
read OUTSIDE; the held descriptor read INSIDE. The Rust helper checks only byte
grammar; the native kernel open enforces containment.

| Host | Policy checks | Replacement checks | Concurrent successes | Concurrent rejections | Link swaps |
|---|---:|---:|---:|---:|---:|
| arm | 416 | 32 | 1467 | 2533 | 952 |
| x86 | 416 | 32 | 1310 | 2690 | 1340 |

Each host ran 16 fresh temporary fixtures with 26 matrix checks each. Each
fixture also checked intermediate symlink replacement and root-name replacement.
Both native CLI checks passed: regular-file acquisition succeeded and strict
symlink acquisition returned failure. Every concurrent success identified the
safe fixture inode. The 4000 attempts per host are schedule samples; acceptance
counts are correctness observations, not performance scores.

Arm host: dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com, AArch64.
xxl resolved to dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com, verified x86_64,
Intel Xeon Platinum 8488C. Both use Linux 6.12.115, GCC 11.5.0, Rust 1.93.1 and
Python 3.9.25. Local uses Rust 1.93.1 and Python 3.13.16. Full host records are
retained under measurements/.

## Oracle and limits

Expected identities come from separately held fixture descriptors using
fstat device/inode pairs. The harness compares opened objects directly and uses
explicit errno expectations. This oracle does not duplicate the candidate's
resolver. Negative controls demonstrate ordinary-open escape, hard-link
acceptance and FIFO acquisition despite successful containment. The FIFO case
then checks type, matching the CLI's requirement to accept regular files.

The mount test uses the host's existing /proc mount. Both hosts executed it;
no privileged mount or namespace setup was performed. Concurrent stress swaps
a directory symlink. Concurrent directory relocation, arbitrary interleavings,
content consistency, hostile device opens and remote-filesystem behavior remain
outside executed coverage. macOS runs portable checks; openat2 requires Linux.
Latency and throughput are unmeasured.

## Validation

The first full-workspace attempt could not unpack a missing dependency into the
read-only user Cargo cache. Those environment failures are retained separately.
The rerun uses a task-local writable Cargo cache with unchanged source and hooks.
See validation-summary.json for the completed workspace gates.

All six workspace gates passed: formatting, Clippy, 573 unit/bin/example tests,
168 doctests, benchmark compilation and warnings-as-errors documentation.
Writing policy and full-branch whitespace checks passed.
