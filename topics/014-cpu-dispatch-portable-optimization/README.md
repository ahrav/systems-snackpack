# CPU dispatch and portable optimization

Portable dispatch has two separate questions:

```text
legal(variant, environment)
profitable(variant, environment, input)
```

CPU and operating-system feature checks establish legality. They do not prove
that the widest legal variant is fastest for a particular CPU or input size.
Keep six concerns separate:

1. a scalar semantic oracle;
2. a deployment baseline that is legal before dispatch runs;
3. isolated specialized variants;
4. feature and execution-state checks;
5. a selection policy;
6. an invocation boundary coarse enough to amortize dispatch.

## Artifact

This crate counts matching bytes through one scalar and one architecture-specific
implementation:

- AVX2 on `x86_64`;
- Advanced SIMD (`neon`) on AArch64.

[`count_eq_scalar`](src/lib.rs) is the oracle.
[`resolve_best`](src/lib.rs) performs runtime legality checks and returns a
[`ResolvedKernel`](src/lib.rs). The function pointer inside `ResolvedKernel` is
private, so safe callers cannot construct a SIMD choice without the matching
feature proof. [`resolve_cached`](src/lib.rs) caches that result for the two
process-stable contracts implemented here.

That cache is not a template for fixed-vector-length Arm Scalable Vector
Extension (SVE) dispatch. Linux SVE vector length is per-thread and can change.
A fixed-vector-length policy must validate the calling thread's current vector
length or use vector-length-agnostic code.

```bash
cargo run -p systems-snackpack-topic-014 --example check_contracts
cargo bench -p systems-snackpack-topic-014 --bench cpu_dispatch -- \
  scalar_simd-p01-1 scalar-vs-simd 1 1 ab scalar_whole
```

The example compares scalar, directly selected, cached, and repeated-detection
paths at vector and chunk boundaries. The experiment disables LLVM loop and
superword-level parallelism (SLP) vectorization in the benchmark build so the
scalar oracle remains a scalar measurement control. That build still uses
explicit AVX2 or Advanced SIMD intrinsics inside the `#[target_feature]`
variant.

## Selection techniques

| Technique | Dispatch boundary | Strength | Main cost or failure |
| --- | --- | --- | --- |
| Conservative baseline | none | one artifact and one code path | leaves legal specialization unused |
| Per-fleet artifact | deployment | permits ordinary inlining and omits a runtime branch | without an enforced feature floor, heterogeneous or drifting fleets can execute illegal code |
| Manual runtime dispatch | caller-selected | can include input size and host policy | detection or indirect calls can leak into inner loops |
| Compiler function multiversioning | function | compiler emits clones and a resolver | feature priority is not workload profitability |
| Executable and Linkable Format (ELF) indirect function (IFUNC) | relocation or lazy binding | steady calls can avoid an explicit feature branch | resolver environment and loader semantics are restrictive |
| glibc-hwcaps shared objects | shared object | ordinary calls after loader selection | duplicates packaged objects and requires synchronized application binary interfaces |

`-C target-cpu=native` is a deployment decision, not runtime dispatch. The
compiler can use enabled instructions before a manual check. Use it only when
the build host's feature set is an enforced deployment floor.

## Legality boundaries

On x86, an AVX-family CPUID bit is insufficient by itself. AVX execution also
requires OS-enabled extended state. The complete predicate checks CPUID leaf
availability, `XSAVE`, `OSXSAVE`, AVX, `XCR0` XMM/YMM state, and the specific
leaf-7 extensions used. Rust's
`is_x86_feature_detected!("avx2")` performs the platform detection; duplicating
the sequence risks executing `XGETBV` before it is legal or omitting required
state.

On Linux AArch64, use the ELF hardware-capability (HWCAP) interface for
architectural feature availability. `HWCAP_SVE` establishes SVE support and
the Linux SVE application binary interface, but not a fixed vector length.
`PR_SVE_GET_VL` reports the calling thread's current vector length.

Rust makes the call contract explicit: invoking a `#[target_feature]` function
without all enabled features is undefined behavior. A function-level
`#[target_feature]` also does not set crate-wide
`cfg(target_feature = "...")`. The checked wrapper must dominate every unsafe
specialized call.

## Cost model

For `N` invocations of input size `n`:

```text
T_branch  = D + N * (h_branch   + T_variant(n) + F_variant(n))
T_pointer = D + N * (h_indirect + T_variant(n) + F_variant(n))
```

`D` is discovery or resolution, `h` is the repeated dispatch boundary, and `F`
is lost optimization such as blocked inlining or extra transitions. If the
baseline and specialized kernels process at rates `r0` and `rk`, a simple
crossover estimate is:

```text
n* = (D_amortized + h + F) / (1/r0 - 1/rk)
```

The denominator must be positive. Even then, the estimate is conditional on
the measured CPU, input distribution, and generated code.

Code size is another budget:

```text
text ~= baseline + sum(specialized variants) + resolver
```

Extra variants increase text size and can displace unrelated hot code. A kernel
microbenchmark does not measure that application-level instruction-cache cost.

## Failure controls

- Build the dispatch wrapper for a conservative deployment baseline. Runtime
  checks cannot rescue a globally over-targeted artifact.
- Test every independent extension used by a variant. AVX2 does not imply
  AES, BMI2, or an AVX-512 subset.
- Hoist discovery and selection outside fine-grained loops. Cached feature
  discovery can still leave branches, calls, and lost inlining.
- Fail closed when a recorded SIMD comparison selects the scalar fallback.
- Keep IFUNC resolvers allocation-free, idempotent, and independent of
  constructors or mutable process state.
- Inspect the linked binary. Source attributes do not prove the final call
  path, vector instructions, or transition cleanup.
- Treat one fresh process as one replicate. Inner iterations amortize timing
  overhead but do not sample startup, placement, or operating-system noise.
- Scope measurements to the exact host, kernel, toolchain, flags, binary,
  input, and run window. A host result is not an instruction-set-architecture
  family claim.

## Focused Linux experiment

The checked-in runner accepts a committed gzip-compressed Git archive and runs
the exact bytes on Linux `x86_64` or AArch64:

```bash
commit=$(git rev-parse HEAD)
git archive --format=tar.gz --output=/tmp/topic14.tar.gz "$commit"
archive_sha=$(sha256sum /tmp/topic14.tar.gz | awk '{print $1}')

SOURCE_ARCHIVE=/tmp/topic14.tar.gz \
  topics/014-cpu-dispatch-portable-optimization/experiment/run_processes.sh \
  /absolute/output requested-host "$commit" "$archive_sha" 0 12
```

The runner verifies the archive and embedded commit, runs repository gates and
the correctness example, records host and compiler evidence, builds a
conservative-baseline benchmark, retains linked disassembly, and executes three
paired comparisons:

1. scalar whole-buffer versus selected SIMD whole-buffer;
2. one selection per whole buffer versus a cached indirect call per 256-byte
   chunk;
3. a cached indirect call versus repeated detection per 256-byte chunk.

Each arm performs eight timed passes over a deterministic 64 MiB buffer. Each
comparison uses 12 fresh-process pairs pinned to one CPU, with six pairs in
each order. The steady interval excludes fixture creation, scalar-oracle
evaluation, and final verification. External process time includes startup and
runner overhead; the residual is mixed and is not reported as pure startup
latency.

Read the [first-visit note](rounds/01.md), [primary-source
ledger](references.md), and [measurement contract](measurements/README.md)
before recording host results.
