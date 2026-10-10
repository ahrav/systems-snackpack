# Primary references

Service documentation checked on 2026-10-10. These are S3 service contracts,
not guarantees about an unpinned SDK or another object-store provider.

- [Multipart overview](https://docs.aws.amazon.com/AmazonS3/latest/userguide/mpuoverview.html): uploader-owned completion receipts, source/part identity and listing boundaries.
- [Multipart limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/qfacts.html): binary part sizes, 10,000 parts and current 48.8 TiB maximum.
- [UploadPart](https://docs.aws.amazon.com/AmazonS3/latest/API/API_UploadPart.html): replacing the same upload ID and part number.
- [CompleteMultipartUpload](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CompleteMultipartUpload.html): ordered ETags, embedded errors and ambiguous missing upload IDs.
- [Conditional writes](https://docs.aws.amazon.com/AmazonS3/latest/userguide/conditional-writes.html): preconditions, 409 and 412 behavior.
- [AbortMultipartUpload](https://docs.aws.amazon.com/AmazonS3/latest/API/API_AbortMultipartUpload.html): in-flight part races and cleanup verification.
- [HeadObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_HeadObject.html): metadata, checksum retrieval permissions and 403/404 boundaries.
- [Upload integrity](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity-upload.html): checksum types and part-number requirements.

The immutable-attempt recovery protocol and timing approximation are application
models derived from these contracts. Local benchmark results are measured facts
about fixture receipt normalization, not S3 performance.
