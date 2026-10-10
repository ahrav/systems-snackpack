# Object-store multipart correctness

The object is not proven published merely because all part requests finished.
Keep unknown completion outcomes distinct from known failures. Freeze source
bytes and completion receipts; reconcile immutable attempt identity; verify
abandoned-part cleanup separately.

This crate is an executable local model, not an S3 client. It contains three
receipt-normalization implementations and a conservative completion classifier.
Numeric tokens stand for opaque ETags, not real hashes. The contract requires
exactly one immutable value for every planned part number 1 through N.
Conflicting duplicate receipts are rejected, even though S3 permits overwriting
a part number. Concurrent writers must be stopped before freezing the manifest.

## Run

```sh
cargo test -p multipart-correctness
cargo run --release -p multipart-correctness --example manifest -- slots 1024 shuffle 4
```

From this topic directory, run a full campaign with a fresh output path:

```sh
python3 run.py /tmp/topic073-results
```

The runner includes compilation, tests, Clippy, input and binary hashes, host
metadata, warmups, 108 fresh measured processes, paired selection, and raw output.
Compiler/profile environment overrides must be empty. Exact build arguments
are retained; the executable is selected from Cargo JSON. See [measurement contract](measurements.md).

## Contracts and failure cases

- Part count is 1 through 10,000; zero/out-of-range/missing numbers fail.
- Identical repeated receipts are accepted. Conflicting tokens fail.
- All three candidates must return the exact ordered oracle manifest.
- HTTP 200 headers, timeouts, 412 and NoSuchUpload do not alone prove success.
- A parsed success or matching immutable identity proves the modeled attempt.
- Identity matching means attempt ID, size, and selected checksum contract.
  A HEAD 403 or incomplete checksum evidence is not absence or a match.
- A definite conditional Complete 409 requires re-initiation for a new attempt.
  Earlier unknown attempts still require reconciliation.
- The model does not implement persistence, network retries, worker cancellation,
  checksum algorithms, version-history reconciliation, or remote cleanup.

## Choosing an implementation

Sorting copies R receipts and normalizes them in O(R log R) work, with O(R)
retained receipt storage. BTreeMap performs O(R log N) work and stores N entries.
Dense slots perform O(R+N) work and store N slots. All include output allocation
and teardown. Slots exploit this application's bounded dense plan. A tree can
serve incremental ordered access, which this finalization benchmark does not
measure. Keep sorting as the simple baseline. Do not infer upload throughput
from local bookkeeping timings.

## S3 boundaries, checked 2026-10-10

Current limits are 10,000 parts, 5 MiB to 5 GiB per non-final part, and 48.8 TiB
maximum object size. The last part has no minimum. Our consecutive numbering is
stricter than some general-purpose bucket modes and compatible with composite
checksums and directory buckets. Specify algorithm and checksum type at initiation.
Full-object and composite checksums are different contracts; an ETag is not a
universal checksum of the body.

An initial 200 response can contain a later embedded completion error. Parse the
body or use a tested SDK. A missing upload ID can mean completed or aborted.
Under a unique immutable key, matching attempt metadata, length, and checksum
can establish success; a single absent read cannot fence late completion.
Mutable pointers need a separate conditional publication/history protocol.

Abort can race with in-flight uploads. Stop producers, settle workers, abort,
and verify that parts are gone; repeat when necessary within a bounded recovery
policy. Retain unresolved cleanup. Aborting parts does not delete a completed
object. Choose lifecycle age from the valid upload and recovery horizon.

## Primary sources

- [Multipart overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html)
- [Multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html)
- [UploadPart replacement](https://docs.aws.amazon.com/AmazonS3/latest/API/API_UploadPart.html)
- [CompleteMultipartUpload response and errors](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html)
- [AbortMultipartUpload and in-flight requests](https://docs.aws.amazon.com/AmazonS3/latest/API/API_AbortMultipartUpload.html)
- [Conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html)
- [Upload integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html)
