# Topic 39 measurement contract

This topic retains correctness and generated-code evidence rather than a
performance ranking. The executable is an unprivileged CPU-side model; it does
not issue DMA or alter IOMMU state. Timing it would measure model arithmetic and
process startup, not device translation behavior.

Each required host runs the exact same Git-created source archive. One fresh
process is one independent correctness replicate. Eight generic and eight
native processes must all match the checked expected output. Native means the
Rust compiler may use features reported by that one host; it does not define a
portable artifact or a processor-family claim.

The retained records include exact source and archive identity, the SSH alias
and resolved hostname, architecture, CPU identity and available count, kernel,
page size, C and Rust toolchains, Rust target configuration, build flags,
visible IOMMU groups and device links, kernel configuration, source manifests,
probe streams, executable hashes, and linked disassembly. Absence of visible
IOMMU groups in this guest-facing environment is not proof that no host IOMMU
exists or that a device bypasses translation.

Host notes and exact-source archives are added only after both required runs
pass. [`../rounds/01.md`](../rounds/01.md) defines the acceptance contract.

The retained records are:

- [`2026-08-18-arm.md`](2026-08-18-arm.md)
- [`2026-08-18-xxl.md`](2026-08-18-xxl.md)
- [`2026-08-18-comparison.md`](2026-08-18-comparison.md)
- Current final-reviewed source binding:
  [`raw/2026-08-18-ef1b55f/SOURCE.md`](raw/2026-08-18-ef1b55f/SOURCE.md)
- Retained post-review source binding, superseded for the current branch head:
  [`raw/2026-08-18-068d082/SOURCE.md`](raw/2026-08-18-068d082/SOURCE.md)
- Retained intermediate source binding, superseded for the current branch head:
  [`raw/2026-08-18-a56a48e/SOURCE.md`](raw/2026-08-18-a56a48e/SOURCE.md)
- Initial retained source binding, also superseded for the current branch head:
  [`raw/2026-08-18-3aaece9/SOURCE.md`](raw/2026-08-18-3aaece9/SOURCE.md)

Both hosts passed the `ef1b55f` exact-source run. Repository history, not the
host bundles, must verify that later evidence-only commits change only evidence
and leave measured source commit
`ef1b55f3cc2b9924e46de035d1f1b2e02e07bb08` unchanged.
