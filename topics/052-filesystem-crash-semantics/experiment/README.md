# Focused Linux correctness experiment

This experiment tests whether one exact native program executes the expected
whole-file replacement order on each required host and whether its application
oracle distinguishes generation 41, generation 42, and corrupt bytes.

It does not freeze storage state. Each cut calls `_exit`, which terminates only
the process. Linux, XFS, the page cache, the controller, and the device remain
live. The observations therefore do not test power loss, filesystem replay,
torn sectors, controller-cache loss, delayed input/output errors, Btrfs, or
OpenZFS.

## Cases and oracles

Every case begins in a fresh block-backed `/var/tmp` directory. The runner reads
the work directory's filesystem type and exits before compiling unless it is
XFS, so a host whose `/var/tmp` moved to Btrfs, overlayfs, or tmpfs cannot
produce a passing receipt for these XFS observations. Initialization writes and
synchronizes generation 41 and its parent directory. The update then writes
checksummed generation 42 to a unique `next.tmp` file.

| Cut | Process exit | Required live-kernel observation |
|---|---:|---|
| after temporary write | 101 | `current` is valid generation 41; temp is present |
| after file `fsync` | 102 | `current` is valid generation 41; temp is present |
| after `renameat` | 103 | `current` is valid generation 42; temp is absent |
| after directory `fsync` | 104 | `current` is valid generation 42; temp is absent |

The after-rename observation proves live namespace visibility only. It does not
predict reboot recovery. The after-directory-sync cut reaches the protocol's
acknowledgement boundary, but the cut still occurs before the example prints an
external acknowledgement.

Two complete fresh directories must produce identical application-oracle
lines. A deliberate one-byte mutation must make the checksum verifier exit 3.
On the required XFS mounts, `cp --reflink=always` must clone one valid record;
mutating the clone must invalidate only the clone. That control demonstrates
range-level reflink isolation for the tested files, not whole-filesystem tree
CoW or crash recovery.

No benchmark is justified for this visit. Code generation is still inspected to
confirm that the compiler and linker retain call instructions to `openat`,
`fsync`, and `renameat`. The checksum path carries no such evidence: `fnv1a` has
internal linkage and is inlined at `-O2`, so the disassembly holds no call to it
and its name survives only in diagnostic strings and debug entries. The
corruption control is what proves that path executed, because a build that
dropped the checksum could not separate a valid record from a one-byte mutation.

## Exact-source run

Run only from a frozen commit. The archive contains Topic 52 and uses a prefix
that binds the full commit:

```bash
commit=$(git rev-parse HEAD)
archive=/tmp/topic52-${commit}.tar.gz
git archive --format=tar.gz \
  --prefix="systems-snackpack-${commit}/" \
  -o "$archive" "$commit" topics/052-filesystem-crash-semantics
archive_sha=$(shasum -a 256 "$archive" | awk '{print $1}')
```

Resolve `xxl` for this run, then record the result before transfer:

```bash
xxl_host=$(ssh xxl hostname -f)
xxl_arch=$(ssh xxl uname -m)
test "$xxl_arch" = x86_64
```

Upload the archive and launcher to a unique exact path. Both commands below run
from the repository root, so the launcher is referenced through its topic path:

```bash
arm=<arm-host-fqdn>
scp "$archive" topics/052-filesystem-crash-semantics/experiment/run_host.sh \
  "$arm:/tmp/"
ssh "$arm" bash /tmp/run_host.sh \
  "/tmp/topic52-${commit:0:7}-arm-receipt" \
  "/tmp/topic52-${commit}.tar.gz" \
  "$arm" "$arm" aarch64 "$commit" "$archive_sha"
```

Use label `xxl`, the freshly resolved hostname, and architecture `x86_64` for
the second target. The runner requires `bash`, `tar`, `rg`, `cc`, `objdump`,
`sha256sum`, `cp --reflink`, `filefrag`, `findmnt`, `hostname`, `uname`,
`mktemp`, `nproc`, `lscpu`, `lsblk`, `df`, `stat`, `cmp`, `awk`, `sort`,
`xargs`, and `date`. It captures `rustc --version` when a Rust toolchain is
present and continues without one, because the probe is C only. It rejects a
hostname, architecture, archive digest, or source layout mismatch before
compiling, requires an XFS work mount, and requires a call instruction to each
synchronization syscall in the disassembly.

## Independent receipt validation

Retrieve each read-only receipt without modifying it, preserving its mode bits.
Validate the expected identity from the controller:

```bash
python3 -I -B topics/052-filesystem-crash-semantics/experiment/validate_receipt.py \
  /path/to/receipt \
  --expected-target-label xxl \
  --expected-hostname "$xxl_host" \
  --expected-architecture x86_64 \
  --expected-source-commit "$commit" \
  --expected-source-archive-sha256 "$archive_sha"
```

The validator rejects a missing seal, a receipt path that carries any write bit,
a symbolic link, an incomplete content manifest, a nested file named after a
root metadata file, a source inventory that disagrees with the retained archive,
changed source, wrong host identity, a missing or duplicated semantic
observation, a missing scope declaration, a failed corruption or reflink
control, or a missing syscall call instruction. Its rejection cases are exercised
by `test_validate_receipt.py`:

```bash
cd topics/052-filesystem-crash-semantics/experiment
python3 -B -m unittest test_validate_receipt
```

Archive and retain the validated receipt before removing its exact remote path.
