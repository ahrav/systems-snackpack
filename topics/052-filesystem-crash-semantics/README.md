# Filesystem crash semantics for copy-on-write filesystems

A filesystem can recover structurally valid metadata while losing an
application update that it had not made durable. Journaling, tree
copy-on-write (CoW), and synchronous logs choose different ways to publish
recoverable filesystem state. An application still needs to order file data,
namespace changes, and its success acknowledgement.

This crate keeps the cost arithmetic and recovery oracle executable. The Linux
experiment applies deterministic process exits to one whole-file replacement
protocol. It does not store the full lesson transcript.

## One update, four different claims

Suppose `catalog.json` names generation 41 and an application wants to publish
generation 42.

- **Runtime atomicity** means a live reader never sees the destination pathname
  missing halfway through replacement.
- **Filesystem consistency** means recovery produces structurally valid
  filesystem metadata.
- **Application durability** means acknowledged generation 42 survives the
  stated failure model.
- **Ordering** means recovery cannot expose the new name without the file state
  on which it depends.
- **Integrity** means the application can detect invalid record bytes. Repair
  requires another valid copy.

These claims compose, but one does not imply the others.

## Four layers that compose

| Technique | Solves | Does not solve | Main catch | Choose it when |
|---|---|---|---|---|
| Metadata journaling | Prevents half-applied in-place metadata changes and bounds replay | Durable application data by default or multi-file application transactions | Journal and checkpoint traffic, pressure, and replay | A mature in-place filesystem matches the workload |
| Tree CoW | Keeps the committed tree while building a replacement tree | Application ordering, arbitrary write atomicity, or media repair | Path-copy amplification, fragmentation, allocation, and reference accounting | Snapshots, reflinks, checksums, and versioned trees justify the cost |
| Intent or tree log | Avoids a full tree or transaction-group commit for each synchronous operation | Asynchronous writes outside the log or undeclared dependencies | Log traffic, replay, capacity limits, and full-commit fallback | Synchronous latency matters and the main commit unit is larger |
| Temporary file, file sync, rename, directory sync | Atomically and durably replaces one pathname under a tested local-filesystem contract | Multi-file atomicity, corruption repair, or power-loss truth on an untested stack | Two persistence barriers, peak old-plus-new space, and cleanup | A configuration, manifest, or checkpoint is replaced as one file |

The fourth row is an application protocol above the first three, not a
competing filesystem implementation.

## The acknowledgement dependency chain

Use a retained descriptor for the destination directory and keep the temporary
file on the same filesystem:

```text
create unique temporary file with O_CREAT | O_EXCL
write every byte, handling short writes
set required mode, owner, and extended attributes
fsync(temporary file)
renameat(parent, temporary, parent, "catalog.json")
fsync(parent directory)
acknowledge generation 42
```

After the file synchronization, generation 42's inode is durable under the
declared stack but `catalog.json` still names generation 41. After `renameat`,
live readers see generation 42 atomically, but the new directory entry is not
yet proven crash-durable. Only the final directory synchronization crosses the
application acknowledgement boundary. A non-interruption synchronization error
leaves persistence uncertain, so the application must not acknowledge success.

Plain `rename` replaces an existing destination. A create-only contract needs
`renameat2` with `RENAME_NOREPLACE` or another no-replace publication primitive.
Multiple files need a higher-level design, such as immutable version files plus
one durably replaced manifest.

## Checked cost questions

First ask how much filesystem-layer traffic a metadata-journal transaction
issues in a simplified model:

```text
ordered mode:      W = D + 2M + C
full data journal: W = 2D + 2M + C
```

`D` is changed user data, `M` is changed metadata, and `C` is journal control
traffic. For `D = 1024 KiB`, `M = 64 KiB`, and `C = 8 KiB`, the models produce
1160 KiB and 2184 KiB. Their payload-relative amplification is 1.133x and
2.133x. The model omits alignment, aggregation, fast commits, allocation,
replication, and device amplification.

Next ask how fixed metadata work affects a tree-CoW update:

```text
W = D + hN + A + R
```

`D` is new file data, `h` is the copied ancestor-node count, `N` is node size,
`A` is auxiliary allocation, checksum, or reference metadata, and `R` is root
publication. A hypothetical 4 KiB update with four 16 KiB nodes, 32 KiB of
auxiliary work, and 4 KiB of root traffic issues 104 KiB, or 26x the payload.
A 1024 KiB update with the same fixed work issues 1124 KiB, or 1.098x. Batching
and locality can dominate the nominal filesystem label.

A synchronous log can acknowledge a small durable representation:

```text
L_log = I / S + F
```

`I` is log traffic, `S` is sequential service rate, and `F` is the stable
storage barrier. A hypothetical 64 KiB log at 500 MiB/s plus a 0.8 ms barrier
takes 0.925 ms in this model. The later main-tree write still exists.

Whole-file replacement has four serial phases:

```text
L_replace = T_write + T_file_sync + T_rename + T_directory_sync
```

Hypothetical phase times of 0.35, 4.80, 0.06, and 0.75 ms total 5.96 ms. These
numbers answer design questions; they are not host measurements.

Run every checked substitution and print the cut-point oracle:

```bash
cargo run -p filesystem-crash-semantics --example crash_costs
```

## Copy-on-write boundaries

Btrfs writes changed data and metadata elsewhere, then publishes a new
generation. Its tree log can satisfy `fsync` without forcing a complete
transaction commit, but namespace dependencies can require a full commit.
Checksums detect covered damage; repair still needs a good replica. Snapshots
and reflinks initially share extents, so they do not create an independent
failure domain. Btrfs `NOCOW` avoids data CoW for selected files but also removes
data checksums and compression.

OpenZFS combines tree CoW with the ZFS Intent Log for synchronous operations.
A separate log device relocates that intent log; it is not a general write
cache. Ext4 usually journals metadata and orders associated data before the
metadata commit; full `data=journal` also journals file data. XFS uses an
asynchronous write-ahead metadata log and supports reflink CoW for shared file
extents. These mechanisms differ, but none removes the application's barrier
contract.

## Focused Linux experiment

The native probe initializes generation 41, writes a checksummed generation 42
to `next.tmp`, and exits at one of four stable cut points. Each fresh case then
checks the destination generation, temporary-file presence, magic, and
checksum. Two complete runs form an A/A control. A deliberate one-byte mutation
must fail the checksum oracle. Where the filesystem supports reflinks, mutating
the clone must leave the source valid.

The required hosts run the same archived source. The receipt records the Git
commit and archive digest, target identity, kernel, processor, compiler and
flags, filesystem and mount options, generated assembly, linked disassembly,
and every semantic result. No elapsed-time comparison is made because this
experiment tests ordering and state classification.

See [the experiment contract](experiment/README.md), [measurement
records](measurements/README.md), and [primary references](references.md).

## Evidence boundary

The deterministic exits terminate one process with `_exit`. Linux, the mounted
XFS filesystem, page cache, controller, and device remain running. Later
writeback can continue. The results therefore do not measure a frozen crash
image, power loss, XFS recovery, Btrfs or OpenZFS recovery, torn sectors,
controller-cache persistence, delayed input/output errors, or hardware flush
truth.

A real recovery claim needs a disposable image or device, recorded persistence
boundaries, an immutable pre-mount cut, and recovery plus application oracles.
Linux `dm-log-writes`, CrashMonkey-style record and replay, or a controlled
power-cut rig can provide that stronger experiment.

## Failure checklist

- A journal commit can be absent or corrupt, and journal pressure can stall
  checkpoint progress.
- A CoW root can be published before every descendant is durable if ordering or
  lower-layer flush behavior is broken.
- Small CoW updates can exhaust metadata workspace despite apparently free
  logical bytes.
- Snapshot retention and reference accounting can turn a local overwrite into
  sustained metadata and space cost.
- A sync log can omit a namespace dependency, fill, fail, or require a full
  transaction fallback.
- Replay must tolerate another crash or fail closed.
- `write` can be short or make zero progress; `close` is not a durability
  barrier.
- Cross-filesystem rename fails with `EXDEV`; stale temporary files require
  startup cleanup.
- A successful checksum detects damage but does not supply repair data.
- Mount-time journal or tree-log replay can modify evidence before inspection.

## Practical rule

Choose a filesystem mechanism for its recovery, integrity, snapshot, and cost
properties. Then define the application's persistent objects and acknowledgement
point independently. For one replaceable object, synchronize the complete new
file, rename it through a retained parent descriptor, synchronize the parent,
and acknowledge only after every required step succeeds. Test that exact
contract on the deployed filesystem and storage stack.
