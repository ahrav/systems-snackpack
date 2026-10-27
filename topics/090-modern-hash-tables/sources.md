# Primary sources

Read on 2026-10-27. Published designs describe their own implementations;
backend widths and erase rules require a pinned source before transfer.

- [Abseil Swiss-table design](https://abseil.io/about/design/swisstables):
  control metadata, short hash fragments, candidate equality and probe termination.
- [Abseil container contracts](https://abseil.io/docs/cpp/guides/container):
  flat/node storage, rehash invalidation and allocation estimates.
- [F14 authors' design](https://engineering.fb.com/2019/04/25/developer-tools/f14/):
  group filtering and payload-layout alternatives.
- [Rust HashMap](https://doc.rust-lang.org/std/collections/struct.HashMap.html):
  equality/hash consistency, stored-key invariants and default hash policy.
- [hashbrown control backend](https://github.com/rust-lang/hashbrown/blob/main/src/control/group/neon.rs):
  current source has a NEON backend; historical claims that Arm always uses a
  scalar fallback must be tied to their version. This experiment makes no
  claim about which backend Rust 1.93.1 selects.
