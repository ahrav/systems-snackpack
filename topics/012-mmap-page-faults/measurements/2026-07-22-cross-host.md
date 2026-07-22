# 2026-07-22 cross-host record

Both hosts ran archive SHA-256
`74738647fce356a0db4e6901f668ea5cb956778030bbc8300187057c16d5a83b`,
whose embedded commit metadata was
`bdd17c6947fbf66207e4bf7204a786d996bad83b`. Each runner verified that its
executing driver matched the archived driver and that source hashes remained
unchanged after the run.

Each condition used eight fresh CPU-0-pinned processes in an order-balanced
eight-block schedule. Touch medians and sample standard deviations below cover
process-to-process variation. They are not confidence intervals and do not
treat the 8,192 pages inside one process as independent samples.

| Condition | AArch64 2b median ± sample SD | x86-64 xlg median ± sample SD | Fault delta in every process |
| --- | ---: | ---: | --- |
| Anonymous first write | 8.782741 ± 0.458700 ms | 14.845655 ± 0.500036 ms | 8,192 minor; 0 major |
| Anonymous refault read | 2.839449 ± 0.029794 ms | 6.882309 ± 0.074915 ms | 8,192 minor; 0 major |
| Resident cached file | 0.428283 ± 0.005926 ms | 1.349075 ± 0.102674 ms | 512 minor; 0 major |
| Verified nonresident file | 4,629.673715 ± 3.235330 ms | 4,722.963079 ± 17.756817 ms | 0 minor; 8,192 major |

The measured invariants match on both hosts:

- Anonymous first write and anonymous refault read produced the same minor-fault
  count but different elapsed time.
- The warm-file scan touched 8,192 pages but produced 512 minor faults.
- Every cold process started `0/8192` resident and ended `8192/8192` resident.
- Every warm-file process started and ended `8192/8192` resident.
- The linked touch loops remained scalar and performed one volatile byte access
  per runtime page stride.

The 512 warm minor faults are consistent with PTE fault-around covering sixteen
4 KiB pages per trap. The count and disassembly are observed; fault-around as
the cause is inferred from upstream Linux v6.18 and is not proven for these
vendor kernels.

The cold mode applies `MADV_RANDOM`. Its 8,192 major-fault deltas and multi-second
elapsed times describe an intentionally sharp mapping-fault workload. Upstream
v6.18 can also account successfully retried faults as major, so the counter is
not a complete I/O trace. The evidence does not establish physical-media-cold
storage or a general major/minor cost ratio.

The timing differences are host-specific. CPU identity, virtualization, NUMA
topology and balancing, generated ISA, and host state differ. They do not rank
AArch64 against x86-64 or ARM against AMD.

Read the [AArch64 record](2026-07-22-dev-dsk-ahrav-2b.md), the
[xlg record](2026-07-22-xlg.md), and the retained
[raw evidence](raw/bdd17c6/).
