# Topic 49 primary sources

Each source supports one bounded mechanism or evidence contract. The checked
measurements remain specific to their recorded hosts, binaries, inputs, and run
windows.

## DRAM commands and timing

- [Samsung DDR4 Device Operation, revision
  1.1](https://download.semiconductor.samsung.com/resources/data-sheet/DDR4_Device_Operations_Rev11_Oct_14-0.pdf)
  defines `ACTIVATE`, `READ`, `WRITE`, `PRECHARGE`, open-row state, and DDR4
  timing rules. It does not define a CPU memory-controller policy.
- [Micron, *DDR5 SDRAM: New
  Features*](https://www.micron.com/content/dam/micron/global/public/products/white-paper/ddr5-new-features-white-paper.pdf)
  describes DDR5 bank groups, short and long command spacing, same-bank and
  all-bank refresh, and one on-die error-correction design. Counts and timings
  vary with density, organization, speed bin, and revision.
- [Intel open-page and close-page policy
  guide](https://www.intel.com/content/www/us/en/content-details/826015/performance-differences-for-open-page-close-page-policy.html)
  documents page-policy choices for one Xeon DDR5 controller. It does not
  establish a policy for other processors.

## Scheduling and loaded operation

- [Rixner et al., *Memory Access Scheduling*, ISCA
  2000](https://repository.rice.edu/items/36e1906f-cadc-4405-a2af-b73ba2340565)
  defines a command scheduler that uses bank state and timing readiness.
- [Mutlu and Moscibroda, *Stall-Time Fair Memory Access Scheduling*, MICRO
  2007](https://users.ece.cmu.edu/~omutlu/pub/stfm_micro07.pdf)
  defines First-Ready, First-Come First-Served ordering as a baseline and
  analyzes its fairness failure. It does not prove that either measured host
  implements the literal policy.
- [Intel Memory Latency
  Checker](https://www.intel.com/content/www/us/en/developer/articles/tool/intelr-memory-latency-checker.html)
  separates idle latency, loaded latency, injection delay, and bandwidth on its
  supported systems. Its output is platform and workload specific.

## Linux placement, counters, and reliability

- [Linux NUMA memory
  policy](https://docs.kernel.org/admin-guide/mm/numa_memory_policy.html)
  defines process and virtual-memory-area placement policy. A NUMA node is not
  a DRAM bank or row.
- [Linux `pagemap`
  documentation](https://docs.kernel.org/admin-guide/mm/pagemap.html) explains
  the capability restriction on physical frame numbers and its RowHammer
  security rationale.
- [Linux HugeTLB
  documentation](https://docs.kernel.org/admin-guide/mm/hugetlbpage.html) and
  [Transparent Huge Page
  documentation](https://docs.kernel.org/admin-guide/mm/transhuge.html) define
  page-size behavior. Huge pages improve translation reach; they do not promise
  row hits or a channel mapping.
- [Linux EDAC](https://docs.kernel.org/driver-api/edac.html), [scrub
  control](https://docs.kernel.org/edac/scrub.html), and [RAS
  guidance](https://docs.kernel.org/admin-guide/RAS/main.html) distinguish
  channels, error reporting, and memory scrubbing. Empty or zero counters do
  not prove an error-correction mechanism is absent.
- [Intel Performance Monitoring Events](https://github.com/intel/perfmon)
  publishes model-versioned core and uncore event definitions. Event names,
  units, scopes, and formulas do not transfer across processor models.
- [Arm Neoverse V1 Core Telemetry
  Specification](https://documentation-service.arm.com/static/65b40f20b52744113be6553e?token=)
  distinguishes core memory accesses, refills, last-level events, and
  translation walks. Core events do not expose DRAM row state.

## Security boundary

- [Kim et al., *Flipping Bits in Memory Without Accessing Them*, ISCA
  2014](https://users.ece.cmu.edu/~omutlu/pub/dram-row-hammer_isca14.pdf)
  demonstrates disturbance errors in its tested device sample. Its prevalence
  and activation counts do not generalize to current memory. This topic does
  not run a RowHammer workload.
