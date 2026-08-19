# Topic 39 measurement contract

This topic retains correctness and generated-code evidence rather than a
performance ranking. The executable is an unprivileged model that runs on the
central processing unit (CPU); it does not issue direct memory access (DMA) or
alter input-output memory management unit (IOMMU) state. Timing the model would
measure arithmetic and process startup, not device translation behavior.

Each required host runs the exact same Git-created source archive. One fresh
process is one independent correctness replicate. A generic build uses the
Rust compiler's default target features, meaning the instruction capabilities
the compiler may assume for that target. A native build adds the build flag
`-C target-cpu=native`; a build flag is an option passed to the compiler, and
this one permits features reported by that one host. Eight fresh processes
from each build mode must match the checked expected output. A native result
does not define a portable artifact, meaning a binary suitable for machines
that provide only the declared baseline capabilities, or a processor-family
claim.

The retained records include exact source and archive identity, the Secure
Shell (SSH) alias and resolved hostname, architecture, CPU identity and
available count, kernel, page size, and C and Rust toolchains, meaning the
compiler, linker, and build-tool versions used to produce the executables. The
records also include Rust target configuration, meaning the destination
architecture and baseline instruction settings; build flags; visible IOMMU
groups, which are kernel isolation sets of devices that cannot be separated by
the IOMMU, and device links, which are filesystem links from a device to its
group. They retain kernel configuration; source manifests, meaning lists of
files and content-fingerprint digests; probe streams, meaning captured standard
output and standard error from the test program; executable hashes; and linked
machine-code inspection, meaning disassembly of the final executable after the
linker resolved its calls. Absence of visible IOMMU groups in this guest-facing
environment is not proof that no host IOMMU exists or that a device bypasses
translation.

Host notes and exact-source archives are added only after both required runs
pass. [`../rounds/01.md`](../rounds/01.md) defines the acceptance contract.

The retained records are:

- [`2026-08-18-arm.md`](2026-08-18-arm.md)
- [`2026-08-18-xxl.md`](2026-08-18-xxl.md)
- [`2026-08-18-comparison.md`](2026-08-18-comparison.md)
- Most recent source binding, the record tying the evidence to one exact source
  commit and archive content fingerprint. Superseded for the current branch
  head: review commits after `2bb0d3e` changed the probe receipt contract, so
  its retained stdout no longer matches `expected.txt` and did not exercise the
  device-reported-descriptor check. Both hosts must be rerun from the current
  head before any binding is the final-reviewed evidence:
  [`raw/2026-08-18-2bb0d3e/SOURCE.md`](raw/2026-08-18-2bb0d3e/SOURCE.md)
- Retained hardened source binding, superseded for the current branch head,
  meaning the latest commit on the topic branch:
  [`raw/2026-08-18-f43f0fe/SOURCE.md`](raw/2026-08-18-f43f0fe/SOURCE.md)
- Retained final-gate source binding, superseded for the current branch head:
  [`raw/2026-08-18-ef1b55f/SOURCE.md`](raw/2026-08-18-ef1b55f/SOURCE.md)
- Retained post-review source binding, superseded for the current branch head:
  [`raw/2026-08-18-068d082/SOURCE.md`](raw/2026-08-18-068d082/SOURCE.md)
- Retained intermediate source binding, superseded for the current branch head:
  [`raw/2026-08-18-a56a48e/SOURCE.md`](raw/2026-08-18-a56a48e/SOURCE.md)
- Initial retained source binding, also superseded for the current branch head:
  [`raw/2026-08-18-3aaece9/SOURCE.md`](raw/2026-08-18-3aaece9/SOURCE.md)

Both hosts passed the `2bb0d3e` exact-source run, and that run remains valid
evidence for commit `2bb0d3e55efda225caeaeafbb285382824692b64` alone. Later
review commits changed the probe's receipt contract, so the current branch head
has no host evidence yet. Repository history, not the host bundles, must verify
that evidence-only commits change only evidence and leave the measured source
commit they name unchanged.
