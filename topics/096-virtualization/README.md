# Virtualization and guest-memory mechanics

The Rust model composes guest and host page mappings, checks write permission at
both stages, and preserves the stage that faults. Toy page sizes make exhaustive
byte-address comparisons practical. The independent oracle expands mappings into
byte entries. The cold-walk enumerator checks g(h+1)+h translation reads.

The Linux probe compares MADV_NOHUGEPAGE and MADV_HUGEPAGE for a deterministic
pointer cycle over 2 MiB and 64 MiB. It requires 4 KiB base pages, aligns each
region to 2 MiB, and uses guard regions to isolate its smaps accounting. Each page
holds one link at a varying cache-line offset. A shuffled permutation checks every
link before timing. The measured traversal performs 128 complete cycles and checks
its result against the arithmetic sum of all page indices.

From the workspace root:

```sh
cargo test -p topic096-virtualization -- --nocapture
cd topics/096-virtualization
cc -O2 -std=c11 -Wall -Wextra -Werror probe.c -o /tmp/topic096-probe
python3 run.py /tmp/topic096-probe > samples.jsonl
```

The runner chooses the lowest allowed CPU and records it. For each footprint it
runs two excluded warmup processes, then six fresh-process pairs in alternating
base/huge and huge/base order. First touch includes link initialization and page
faults. Steady timing includes dependent loads, address calculation, and checksum
addition after one complete verification traversal. Compilation, allocation,
permutation construction, smaps reading, and process launch are outside timing.

Declare a descriptive winner only if all six paired differences exceed 5 percent
in the same direction. All six differences within 5 percent is a practical tie;
other patterns are unresolved. This small campaign describes these processes on
these hosts. It does not estimate population confidence or application tails.

AnonHugePages observations apply to this process mapping. They establish neither
host-stage page size nor exact hardware TLB coverage. A zero value alone cannot
exclude PTE-mapped multi-size THP. The experiment retains actual observations and
limits attribution to the requested guest-side memory policy. See results.md.

## Sources

- [KVM MMU](https://docs.kernel.org/virt/kvm/x86/mmu.html): nested walks and shadow paging.
- [KVM API](https://docs.kernel.org/virt/kvm/api.html): memory slots, execution, and dirty tracking.
- [Linux THP](https://docs.kernel.org/admin-guide/mm/transhuge.html): policy, mapping, and allocation costs.
- [QEMU migration](https://www.qemu.org/docs/master/devel/migration/main.html): live state transfer.
- [Nested KVM](https://docs.kernel.org/virt/kvm/x86/running-nested-guests.html): host and guest prerequisites.
