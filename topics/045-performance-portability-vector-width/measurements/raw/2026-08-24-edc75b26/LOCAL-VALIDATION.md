# Local and collection validation

Date: 2026-08-24

## Repository gates

The publication branch passed:

```text
git diff --check
cargo fmt --all -- --check
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo clippy --workspace --all-targets -- -D warnings
cargo bench --workspace --no-run
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps
```

The Topic 45 package passed four unit tests and four doctests. Both shell scripts
passed `bash -n`; all four Python scripts passed syntax compilation; and the
protocol self-test retained and serialized a forced timeout and confirmed that
malformed numeric result output is treated as invalid rather than raising an
exception. Strict source and documentation reviews found no unresolved factual,
evidence-boundary, or plain-language blockers.

## Checked-source host commands

Both hosts extracted the same scoped archive and ran its archived runner outside
the repository. The source and archive use Secure Hash Algorithm 256-bit
(SHA-256) digests. The fixed invocation shape was:

```text
SOURCE_COMMIT=edc75b260d1909bb9c4d043cbfadba5e98e38944
SOURCE_ARCHIVE_SHA256=1c1f7c89a513ec6409367b3b5605def6748ba95d2a9f1a55fcfe67c111031852
SOURCE_ARCHIVE_PATH=/tmp/topic45-source-edc75b26.tar.gz
SSH_TARGET_LABEL=<recorded-target>
SSH_RESOLVED_HOSTNAME=<recorded-runtime-hostname>
run_host.sh /tmp/<fresh-attempt-directory> <pinned-cpu> 20000000
```

The x86 process used central processing unit (CPU) 24 through target label
`xxl`. The Arm process used CPU 16 through the fixed authorized hostname. Each
runner compiled with the recorded flags, checked every supported mode against
the scalar oracle, captured final-image disassembly, ran the fixed process
schedule, checked source and binary stability, and wrote `status=PASS` only
after receipt validation.

## Collection gates

Collection performed these checks before retaining the evidence:

- matched each downloaded bundle's SHA-256 digest to the digest computed on its
  host;
- rejected unsafe, duplicate, unsupported, or wrong-root archive members before
  extraction;
- matched each bundle's embedded source archive byte for byte with
  `source.tar.gz`;
- required exact `status=PASS` bytes and a passing host validation report;
- ran the validator from the archived source with the expected commit, archive
  digest, target label, and resolved hostname;
- matched each independent report byte for byte with its host-side report; and
- regenerated and checked `SHA256SUMS` for every retained input and report.

## Superseded attempts

Commit `293f73f` completed its workloads but its host validator used
`zip(..., strict=True)`, which Python 3.9 does not implement. Commit `86b8ab2`
replaced that call and passed both host validators, but one standard-deviation
value had a different final rendered digit on the Arm host and x86 collection
runtime. Those reports were not byte-identical.

Commit `39cc504f` produced byte-identical passing reports, but strict source
review then required documentation corrections. Commit `5acba778` also passed
on both hosts, but review exposed missing archive-member checks, an incomplete
Arm generated-code screen, and a malformed-output retention gap. Those attempts
remain preserved as superseded evidence and support no publication claim.

Commit `edc75b260d1909bb9c4d043cbfadba5e98e38944` includes the final source
corrections. Its fifth fresh attempt produced byte-identical host and offline
reports on both architectures. Only this attempt supports the retained
measurement claims.
