# Primary references

- [Linux `fsync(2)`](https://man7.org/linux/man-pages/man2/fsync.2.html) defines
  the file and directory synchronization boundary used by the replacement
  protocol.
- [Linux `rename(2)`](https://man7.org/linux/man-pages/man2/rename.2.html)
  defines live namespace replacement and the same-filesystem constraint.
- [ext4 journal design](https://docs.kernel.org/filesystems/ext4/journal.html)
  distinguishes metadata journaling, ordered data, and full data journaling.
- [XFS delayed logging](https://docs.kernel.org/filesystems/xfs/xfs-delayed-logging-design.html)
  describes its asynchronous write-ahead metadata log.
- [Btrfs design](https://btrfs.readthedocs.io/en/stable/dev/dev-btrfs-design.html)
  describes generation publication and tree copy-on-write.
- [`btrfs(5)`](https://btrfs.readthedocs.io/en/latest/btrfs-man5.html) describes
  tree-log replay and the `NOCOW` integrity tradeoff.
- [Btrfs checksumming](https://btrfs.readthedocs.io/en/stable/Checksumming.html)
  distinguishes detection from replica-based repair.
- [Btrfs subvolumes](https://btrfs.readthedocs.io/en/latest/btrfs-subvolume.html)
  documents snapshot sharing and commit behavior.
- [OpenZFS copy-on-write](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Copy-on-write.html)
  describes tree publication through new blocks.
- [OpenZFS caching and the ZFS Intent Log](https://openzfs.github.io/openzfs-docs/Basic%20Concepts/Pool%20Structure/Caching.html)
  scopes the synchronous intent log and separate log device.
- [All File Systems Are Not Created Equal](https://www.usenix.org/conference/osdi14/technical-sessions/presentation/pillai)
  motivates testing application persistence properties per filesystem.
- [CrashMonkey](https://www.usenix.org/conference/osdi18/presentation/mohan)
  demonstrates persistence-boundary record and replay for real crash testing.
- [Linux `dm-log-writes`](https://docs.kernel.org/admin-guide/device-mapper/log-writes.html)
  documents a disposable-device write-order recorder for stronger tests.

Sources were checked on 2026-08-31. The artifact treats current documentation
as mechanism evidence, not as measured behavior on the experiment hosts.
