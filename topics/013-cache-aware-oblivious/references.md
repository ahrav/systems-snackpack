# Primary sources

- [Aggarwal and Vitter, *The Input/Output Complexity of Sorting and Related
  Problems*](https://doi.org/10.1145/48529.48535): the external-memory transfer
  model that preceded cache-oblivious analysis.
- [Prokop, *Cache-Oblivious Algorithms*](https://dspace.mit.edu/handle/1721.1/1197):
  ideal-cache assumptions, tall-cache bounds, recursive transpose, and
  van Emde Boas layout.
- [Frigo, Leiserson, Prokop, and Ramachandran, *Cache-Oblivious
  Algorithms*](https://doi.org/10.1145/2071379.2071383): multilevel transfer
  bounds without cache parameters.
- [Bender, Demaine, and Farach-Colton, *Cache-Oblivious B-Trees*](https://doi.org/10.1137/S0097539701389956):
  search and update structures in the ideal-cache model.
- [Rao and Ross, *Making B+-Trees Cache Conscious in Main Memory*](https://doi.org/10.1145/342009.335449):
  cache-aware node layout and pointer-elimination tradeoffs.
- [Khuong and Morin, *Array Layouts for Comparison-Based Searching*](https://arxiv.org/abs/1509.05053):
  measured search-layout tradeoffs beyond asymptotic transfer counts.
- [Lam, Rothberg, and Wolf, *The Cache Performance and Optimizations of Blocked
  Algorithms*](https://doi.org/10.1145/106972.106981): blocking, interference,
  and cache-conflict analysis.
- [Rivera and Tseng, *Tiling Optimizations for 3D Scientific
  Computations*](https://doi.org/10.1109/SC.2000.10015): array padding as a
  conflict-reduction technique.
- [Linux cache sysfs ABI](https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-devices-system-cpu):
  exported cache level, size, line, set, associativity, and sharing fields.
- [Linux pagemap documentation](https://www.kernel.org/doc/html/latest/admin-guide/mm/pagemap.html):
  PFN access restriction and zeroed PFNs for unprivileged callers.
- [Linux transparent huge-page documentation](https://www.kernel.org/doc/html/latest/admin-guide/mm/transhuge.html):
  advice, policy, collapse, split, and verification boundaries.
- [Arm Neoverse V1 Technical Reference Manual](https://developer.arm.com/documentation/101427/latest/):
  implementation-specific L1 and L2 organization and replacement behavior.
- [Intel 64 and IA-32 Architectures Software Developer's
  Manual](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html):
  deterministic cache-parameter enumeration.
- [AMD CPUID Specification, publication 25481](https://www.amd.com/content/dam/amd/en/documents/archived-tech-docs/design-guides/25481.pdf):
  extended deterministic cache-parameter enumeration.

The algorithmic bounds use the models and assumptions in the cited papers.
Recorded hardware evidence uses each host's exported geometry and linked
generated code. Neither source establishes an undocumented physical
address-to-shared-cache mapping.
