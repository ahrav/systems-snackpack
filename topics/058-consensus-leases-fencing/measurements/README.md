# Evidence

Initial scratch runs on both required Linux hosts passed the lease-pause and
joint-quorum example before repository mutation. Their common source SHA-256 is
`e924e95e7f6fce605169615afa27e654a45435459f098943ec99e8416d087b3f`.

The committed-source campaign is recorded after the source commit. It uses
`experiment/run_host.sh` to check host, architecture, archive, runner, source,
correctness, and generated-code identities. Full receipts and replay assets are
retained outside Git; compact results and their exact identities are added here.

This is deterministic correctness evidence. There are no measured network,
lease-expiry, failover, disk-durability, or cross-architecture performance claims.

## Committed-source result

Source commit: `4fe5b86c75345beebfc2fa7ea2a6d4e2d6ec0ac8`.
Archive SHA-256: `0e2348c601df6f4ee188dd30b678b92df5695a34aac996b22cb49a435ccc5348`.
Runner SHA-256: `a3e789b886a94aad63220b3446d9323df5669d8d4b710663e4b5b99de5972864`.

Both hosts passed 11 tests, one doctest, and the same asserted example. Each sealed
receipt has ten files whose hashes, source identity, host, and architecture were
verified after retrieval. There was one deterministic campaign per host. There
are no independent timing samples or performance dispersion to report.

| Host | Processor identity | Available CPUs | Linux kernel | Rust |
|---|---|---:|---|---|
| Named Arm host | ARM model 1; implementer `0x41`, part `0xd40`, revision 1 | 64 | `6.12.103-127.188.amzn2023.aarch64` | 1.98.1 |
| Runtime-resolved `xxl` | Intel Xeon Platinum 8488C, model 143 | 192 | `6.12.103-127.188.amzn2023.x86_64` | 1.98.0 |

Exact hostnames, compiler commits, default target features, processor flags, and
build flags are in the host files. Builds use the generic target processor,
optimization level 2, and no link-time optimization. Tests are unoptimized.

The inspected out-of-line generation predicate lowered to `cmp/ccmp/cset` on
this Arm compiler and `test/setne/cmp/sete/and` on this x86 compiler. Both encode
nonzero-and-equal acceptance. These instructions neither authenticate a grant
nor make a separate storage effect atomic. The assembly is evidence of these
specific builds, not an instruction-set performance comparison.

All required workspace gates passed. Two local scratch mutants were caught:
removing generation enforcement failed four tests, and replacing the joint rule
with a union majority failed three. Original sources were unchanged.

Full archives, binaries, assembly, and original receipt files are retained at:

```text
/Users/ahrav/.codex/learning/advanced-systems-evidence/topic-058/2026-09-09-4fe5b86c
```

`results.json` names the exact receipt and retained-checkpoint hashes. Compact
text copies remove trailing whitespace and terminal blank lines. `arm-SHA256SUMS`
and `xxl-SHA256SUMS` identify the original receipt bytes, not the normalized copies.

## Replay on an isolated Linux directory

From a fresh scratch directory, create the path-limited archive and runner from
an existing clone (replace `/path/to/systems-snackpack` with that clone):

```bash
git -C /path/to/systems-snackpack archive --format=tar --prefix=source/ \
  4fe5b86c75345beebfc2fa7ea2a6d4e2d6ec0ac8 \
  topics/058-consensus-leases-fencing > source.tar
git -C /path/to/systems-snackpack show \
  4fe5b86c75345beebfc2fa7ea2a6d4e2d6ec0ac8:topics/058-consensus-leases-fencing/experiment/run_host.sh \
  > run_host.sh
```

Transfer both files into a new isolated directory on the expected Linux host.
Invoke there:

```bash
bash run_host.sh "$EXPECTED_HOST" "$EXPECTED_ARCH" \
  4fe5b86c75345beebfc2fa7ea2a6d4e2d6ec0ac8 \
  0e2348c601df6f4ee188dd30b678b92df5695a34aac996b22cb49a435ccc5348 \
  a3e789b886a94aad63220b3446d9323df5669d8d4b710663e4b5b99de5972864
```

Set `EXPECTED_HOST` to the actual fully qualified hostname and `EXPECTED_ARCH` to
`aarch64` or `x86_64`. Keep the recorded values when replaying on the same hosts.
The runner refuses mismatches and requires a new directory without `receipt/`.
