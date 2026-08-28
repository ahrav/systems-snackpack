# Topic 48 primary sources

Each source supports one contract or architecture boundary. Numeric results in
the checked measurements remain specific to the recorded hosts and binaries.

## Compiler and language contracts

- [GCC 11.5 `__builtin_prefetch`](https://gcc.gnu.org/onlinedocs/gcc-11.5.0/gcc/Other-Builtins.html)
  defines the read/write and locality arguments used by the experiment. It
  permits a target to omit a prefetch instruction and states that the address
  expression is still evaluated.
- [Arm C Language Extensions](https://arm-software.github.io/acle/main/acle.html)
  define Arm prefetch intrinsics and permit implementations to treat them as
  no-ops.
- [Rust x86-64 `_mm_prefetch`](https://doc.rust-lang.org/stable/core/arch/x86_64/fn._mm_prefetch.html)
  documents the stable x86 intrinsic.
- [Rust AArch64 `_prefetch`](https://doc.rust-lang.org/core/arch/aarch64/fn._prefetch.html)
  documents the current nightly-only AArch64 intrinsic boundary.
- [Rust pointer `add`](https://doc.rust-lang.org/std/primitive.pointer.html#method.add)
  defines when forming an offset pointer is valid. A prefetch hint does not
  relax that source-language requirement.

## Architecture and processor boundaries

- [Intel 64 and IA-32 Optimization Reference Manual, Volume 1, version
  050](https://cdrdv2-public.intel.com/821612/248966-Optimization-Reference-Manual-V1-050.pdf)
  covers regular hardware-prefetch patterns, software-prefetch distance, cache
  pollution, and bandwidth costs.
- [Intel Software Developer's Manual, Volume 2A, version
  088](https://cdrdv2-public.intel.com/858446/253666-088-sdm-vol-2a.pdf)
  defines the `PREFETCHh` hint and its implementation-dependent locality.
- [Intel Sapphire Rapids last-level-cache prefetch technical
  brief](https://cdrdv2-public.intel.com/780991/780991-Hardware_LLC_prefetch__4th_Gen_Intel_Xeon_Scalable_Processor-R1_0.pdf)
  documents one optional generation-specific page-prefetch feature, its
  default state, and bandwidth cautions. It does not describe all Intel hosts.
- [Arm Neoverse V1 Technical Reference
  Manual](https://documentation-service.arm.com/static/6088335985368c4c2b1c266d)
  describes the measured Arm core's load hardware prefetch and `PRFM` behavior.
- [Arm Architecture Reference Manual for A-profile](https://developer.arm.com/documentation/ddi0487/latest)
  defines the architectural `PRFM` hint and exception boundary.

## Irregular-access designs

- [Chen, Ailamaki, Gibbons, and Mowry, *Improving Hash Join Performance through
  Prefetching*](https://doi.org/10.1145/1272743.1272747) studies group prefetch
  and software-pipelined hash joins on the paper's systems.
- [Cimple: Instruction and Memory Level
  Parallelism](https://arxiv.org/abs/1807.01624) describes software-pipelined
  concurrent traversal of irregular structures. Its measured crossovers do not
  transfer to current machines without replication.
