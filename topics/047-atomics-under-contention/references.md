# Topic 47 primary sources

Each source below supports one boundary. Performance numbers remain specific to
the cited machines or the checked-source measurements in this topic.

## Language and compiler contracts

- [Rust atomic module](https://doc.rust-lang.org/std/sync/atomic/) guarantees
  that available atomic types are lock-free but not necessarily wait-free. It
  also explains that operations implemented with compare-and-swap loops need
  not give each thread a completion bound.
- [Rust `Ordering`](https://doc.rust-lang.org/std/sync/atomic/enum.Ordering.html)
  defines `Relaxed` atomicity without ordering constraints for other memory.
- [Rust `AtomicU64`](https://doc.rust-lang.org/std/sync/atomic/type.AtomicU64.html)
  defines `fetch_add`, weak compare-and-swap failure, and the success/failure
  ordering contracts.
- [LLVM atomic instruction and code-generation
  guide](https://llvm.org/docs/Atomics.html) documents compiler intermediate
  representation semantics and common target lowering. Exact linked code still
  depends on compiler revision, target features, and optimization.

## Architecture boundaries

- [Arm `LDADD` instruction
  reference](https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/LDADD--LDADDA--LDADDAL--LDADDL--Atomic-add-on-word-or-doubleword-in-memory-)
  defines the relaxed, acquire, release, and acquire-release Large System
  Extensions (LSE) atomic-add forms.
- [Arm compare-and-swap (CAS) instruction
  reference](https://developer.arm.com/documentation/ddi0602/latest/Base-Instructions/CAS--CASA--CASAL--CASL--Compare-and-swap-word-or-doubleword-in-memory-)
  defines the corresponding compare-and-swap forms.
- [Arm's GNU Compiler Collection (GCC) LSE implementation
  note](https://developer.arm.com/community/arm-community-blogs/b/tools-software-ides-blog/posts/making-the-most-of-the-arm-architecture-in-gcc-10)
  contrasts direct LSE code with load-exclusive/store-exclusive loops and
  runtime-selected out-of-line atomics.
- [Linux AArch64 processor identifiers](https://github.com/torvalds/linux/blob/master/arch/arm64/include/asm/cputype.h)
  map Arm implementer `0x41` and part `0xd40` to Neoverse V1. This identifies
  the observed model register; it does not generalize a timing result.
- [Intel 64 and IA-32 Software Developer's Manuals, revision
  092](https://www.intel.com/content/www/us/en/developer/articles/technical/intel-sdm.html)
  define locked-operation ordering and distinguish cache locking from external
  bus locking. Apply model-specific implementation guidance only to identified
  Intel processors.
- [AMD64 Architecture Programmer's Manual, Volume
  1](https://docs.amd.com/v/u/en-US/24592_3.24) defines AMD locked
  read-modify-write and ordering behavior. It does not establish Intel
  microarchitecture behavior.

## Contention and alternative ownership

- [David, Guerraoui, and Trigonakis, *Everything You Always Wanted to Know
  About Synchronization but Were Afraid to Ask*](https://infoscience.epfl.ch/server/api/core/bitstreams/68bfb25e-25de-4743-85d3-17b9a56ef068/content)
  measures operation- and topology-dependent atomic scaling on its 2013 test
  systems. Its numeric results do not transfer to current hosts.
- [Anderson, *The Performance of Spin Lock Alternatives for Shared-Memory
  Multiprocessors*](https://homes.cs.washington.edu/~tom/pubs/spinlock.pdf)
  analyzes centralized spinning and exponential backoff on the paper's
  machines.
- [Mellor-Crummey and Scott, *Algorithms for Scalable Synchronization on
  Shared-Memory Multiprocessors*](https://www.cs.rochester.edu/~scott/papers/1991_TOCS_synch.pdf)
  gives queue locks whose waiters spin on separate locations. Queue locks add
  predecessor and scheduling dependencies.
- [Hendler, Incze, Shavit, and Tzafrir, *Flat Combining and the
  Synchronization-Parallelism Tradeoff*](https://doi.org/10.1145/1810479.1810540)
  studies one combiner applying published operations. Its measured crossover
  belongs to the paper's data structures and machines.
- [Linux `this_cpu` operations](https://www.kernel.org/doc/html/latest/core-api/this_cpu_ops.html)
  explain how updates local to one central processing unit (CPU) avoid one
  shared line and move cost to aggregation. Kernel preemption rules do not
  transfer directly to user-space CPU indexing.
- [Java `LongAdder`](https://docs.oracle.com/en/java/javase/24/docs/api/java.base/java/util/concurrent/atomic/LongAdder.html)
  states the sharded-counter contract: statistics rather than fine-grained
  synchronization, with higher space use and aggregate reads.
- [Linux mutex design](https://www.kernel.org/doc/html/latest/locking/mutex-design.html)
  describes atomic fast paths, optimistic spinning, and sleeping slow paths.
  Rust's mutex implementation and fairness remain platform-specific.
