# Exact-source host comparison

Both required hosts built the same archived source and passed the same
correctness oracles.

| Check | Arm | `xxl` |
|---|---|---|
| source and archive identity | pass | pass |
| four deterministic exit codes | 101, 102, 103, 104 | 101, 102, 103, 104 |
| pre-rename destination | valid generation 41 | valid generation 41 |
| post-rename destination | valid generation 42 | valid generation 42 |
| complete A/A control | identical | identical |
| corruption rejection | exit 3 | exit 3 |
| reflink clone isolation | pass | pass |
| code-generation paths | retained | retained |
| independent sealed validation | 50 files | 50 files |

The matching observations show that the exact application protocol and oracle
behaved alike in these two run windows. They do not establish an
instruction-set property. The hosts differ in processor topology, kernel
build, virtual-machine configuration, storage size, and Rust toolchain.

Both runs used XFS and process exits on a live kernel. They do not measure Btrfs
or OpenZFS recovery, power-loss durability, XFS replay, or device-level write
ordering. No elapsed-time comparison was collected or inferred.
