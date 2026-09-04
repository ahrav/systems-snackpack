# Focused Linux correctness experiment

The native probe uses the `io_uring` system calls directly. It needs no
liburing installation. One process runs four checks and exits nonzero if any
oracle fails.

## Checks

1. Create an eight-entry baseline ring and report the returned SQ, CQ, and
   feature fields.
2. Create a `SINGLE_ISSUER` ring. Submit one no-op from the owner, then require
   a second task's submission to fail with `EEXIST`.
3. Create a `SINGLE_ISSUER | DEFER_TASKRUN` ring. Submit a 20-millisecond
   timeout, remain in userspace for 80 milliseconds, require zero visible CQEs,
   then enter with `GETEVENTS` and require the terminal `ETIME` CQE.
4. Submit a five-second timeout with token `0x3001`. Submit async cancel with
   token `0x3002`. Drain both CQEs. Require cancel result zero and target result
   `ECANCELED`, independent of CQE order.

The source fills each SQE before a release store publishes the SQ tail. The
probe does not enable submission queue polling. An `SQPOLL` producer also
needs the documented post-publication barrier, `IORING_SQ_NEED_WAKEUP` check,
and conditional wakeup; this probe makes no claim about that path.

## Boundary

This experiment checks capability and correctness on one exact kernel and
security context. It does not benchmark performance. It does not test a block
device, sockets, registered resources, CQ overflow, multishot operations,
provided buffers, seccomp filters, or Linux Security Module rules. The returned
feature mask does not prove that every setup flag or opcode works.

## Local build

```bash
cc -O2 -g -std=c11 -Wall -Wextra -Werror -pthread \
  experiment/io_uring_lifetimes.c \
  -o /tmp/io_uring_lifetimes
timeout 10s /tmp/io_uring_lifetimes
```

Expected semantic lines are:

```text
baseline_setup=ok ...
single_issuer ... other_task_enter=-17 (File exists)
defer_taskrun cqes_before_getevents=0 ... res=-62
cancel ... one result 0 ... one result -125
result=ok
```

Completion order can differ. The runner checks tokens and results instead of
requiring one order.

## Exact-source host run

Create a path-limited archive only after committing the probe and runner:

```bash
commit=$(git rev-parse HEAD)
archive=/tmp/topic54-${commit}.tar.gz
git archive --format=tar.gz \
  --prefix="systems-snackpack-${commit}/" \
  -o "$archive" "$commit" topics/054-io-uring-lifetimes
archive_sha=$(shasum -a 256 "$archive" | awk '{print $1}')
```

Transfer the archive and exact committed `run_host.sh` to each declared host.
Before extracting, the runner verifies the archive digest, Git commit header,
path-limited member set, member types, and size bounds. It then verifies the
hostname, architecture, archived launcher identity, source inventory, result
oracles, assembly, and linked disassembly. It writes a manifest-covered
read-only receipt.

```bash
bash /tmp/run_host.sh \
  /tmp/topic54-receipt \
  /tmp/topic54-${commit}.tar.gz \
  arm \
  dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
  aarch64 \
  "$commit" \
  "$archive_sha"
```

Resolve `xxl` at run time. Pass label `xxl`, its resolved fully qualified
hostname, and architecture `x86_64` for the second receipt.

Retrieve the read-only receipt without changing its mode bits. Validate it on
the controller:

```bash
python3 -I -B experiment/validate_receipt.py \
  /path/to/receipt \
  --expected-target-label xxl \
  --expected-hostname "$xxl_host" \
  --expected-architecture x86_64 \
  --expected-source-commit "$commit" \
  --expected-source-archive-sha256 "$archive_sha"
```

The validator derives the expected source inventory from the retained archive.
It rejects changed or fabricated inventories, extra probe output, an incomplete
content manifest, writable receipt entries, links, a wrong archive or runner,
identity mismatches, missing scope exclusions, and any failed semantic oracle.
Its focused tests cover both valid cancellation-CQE orders, a missing target
terminal CQE, and contradictory extra output:

```bash
cd experiment
python3 -B -m unittest test_validate_receipt
```
