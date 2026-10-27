# Topic 090 plugin finding

No change is justified for this lesson at origin/main `dddaa073e83b876c64d16988057362b86aa11125`.
The existing owner is `low-level-systems:systems-data-structures`.

- The entrypoint names SwissTable, load factor, tombstones, HashDoS and Robin Hood.
  Its selection table routes map semantics, control bytes and mutation to the
  corresponding existing references. Those linked files exist at this revision.
- `hash-table-internals.md` covers Eq/Hash consistency, stable stored keys,
  adversarial hashing, reference stability, capacity, churn and concurrent maps.
- `swisstable-and-f14-internals.md` covers version-specific group widths, high-bit
  tags, candidate/equality distinction, EMPTY/DELETED termination, F14 overflow
  differences and conditional tag-collision expectations. It explicitly separates
  reduced comparison counts from measured latency.
- `open-addressing-mutation.md` already contains the 1/9/17 tombstone witness,
  search-before-reuse, full-table bounds, cyclic deletion repair, live/nonempty
  occupancy and complete rebuild accounting. It warns against transferring
  insertion-only probe formulas to arbitrary churn.
- `robin-hood-contracts.md` supplies the separate displacement invariant,
  lookup stop, deletion repair and unchanged-failure contract.

The inspected primary sources support the lesson's mechanism claims. Existing
references pin their historical source details and require deployment-version
verification. Today's scalar experiment supplies measurements for a lesson;
it creates no missing skill contract. No plugin files, manifests or eval cases
were changed. No paired skill evaluation is applicable. This is a source and
routing-link audit; runtime routing accuracy and behavioral lift were not measured.
Blob identities are retained in `plugin-audit.json`.
