# Rust aliasing and pointer provenance

A Rust pointer is not only a numerical address. It also carries abstract
permission information that constrains which memory it may access, when, and
whether it may write. That information is called **provenance**. **Aliasing**
means that two access paths can reach overlapping memory. These rules matter
because unsafe code must uphold the reference promises and raw-access
preconditions that the compiler may rely on. Code can print the expected value
and still have undefined behavior, which means Rust assigns no requirements to
what the program does.

Use a hotel keycard as the running model. The room number is the address. The
keycard's authorization is the provenance. Two cards can print the same room
number without granting the same access. A card can also expire while its room
number remains unchanged.

## Keep the access contract visible

For the ordinary, non-volatile loads and stores in this topic, establish all of
these conditions:

1. the pointer is non-null when the operation requires it;
2. its address is aligned for the value type;
3. the operation permits access to the entire byte range, which for normal
   memory means that range lies inside one live allocation;
4. a read produces an initialized, valid value of the requested type;
5. the pointer's provenance permits that access;
6. the access does not violate active reference or interior-mutability rules;
7. no unsynchronized conflicting access creates a data race.

A shared reference, `&T`, grants shared access and normally prevents mutation
of its value. `UnsafeCell<T>` is the standard exception for interior
mutability, meaning mutation through a shared outer reference. A mutable
reference, `&mut T`, grants exclusive access for its live use. Derived
reborrows are valid; independent overlapping access paths are not. The exact
general alias model remains under specification, so this topic states only the
reference contracts needed by its code.

Raw pointers, `*const T` and `*mut T`, let code express operations that the
borrow checker cannot prove. They remove static checking at that point; they
do not remove the access conditions above.

## Choose the narrowest representation

| Technique | Problem solved | How it works | Does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| Safe borrowing and slice splitting | Prove disjoint access | APIs such as `split_at_mut` create non-overlapping references | Foreign layouts or address-only interfaces | The program must fit the safe API's ownership shape | Safe code can express the partition |
| Strict Provenance pointer operations | Manipulate an address while retaining known provenance | `addr` extracts the numerical address; `with_addr` and `map_addr` form a pointer that copies the carrier's provenance | Bounds, alignment, initialization, or aliasing | The derived address still must name memory that the copied provenance permits the operation to access | Low-level code has a real pointer that can remain the provenance carrier |
| Exposed Provenance operations | Reconstruct a pointer when an address crossed an integer-only boundary | `expose_provenance` records exposure and `with_exposed_provenance` asks the implementation to select a previously exposed provenance | Proof that a dereference is valid | Selection has weaker, deliberately ambiguous semantics and is harder for tools to reason about | An operating-system or foreign interface truly erases the pointer carrier |
| Raw pointers | Express overlap, optionality, or foreign memory | The programmer performs loads and stores under a written safety contract | Any validity rule | Reviewers and tools must reconstruct every obligation | Safe borrowing cannot express the required layout or protocol |
| `UnsafeCell<T>` | Permit controlled mutation behind shared access | It opts its contained value out of the usual shared-reference immutability promise | Overlapping `&mut`, invalid lifetimes, or data-race safety | The surrounding abstraction must supply synchronization and invariants | Interior mutability is the intended API contract |
| `NonNull<T>` | Store a non-null raw pointer efficiently | It wraps a raw pointer and lets `Option<NonNull<T>>` use null as its discriminant | Liveness, alignment, initialization, ownership, or dereference validity | Its covariance can make an abstraction that mutates `T` unsound | Non-nullness is a useful representation invariant |
| Indices or handles | Survive relocation, serialization, or shared-memory remapping | Store a logical identifier and resolve it through a current owner | Stable address identity by itself | Every use needs validated resolution and generation rules | Data can move or cross process boundaries |

`Pin`, `MaybeUninit`, and atomics solve different problems. `Pin` prevents safe
code from moving a pinned `!Unpin` value through the pinned handle.
`MaybeUninit` represents bytes that may not yet hold a valid value. Atomic
operations coordinate concurrent accesses. None creates valid provenance or
repairs an invalid aliasing relationship.

## Separate semantic permission from generated code

The example exports two small contracts. The reference version requires the
destination and source to be distinct. The raw-pointer version explicitly
permits exact overlap.

```rust
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic42_reference_contract(destination: &mut u64, source: &u64) -> u64 {
    let first = *source;
    *destination = first.wrapping_add(1);
    first.wrapping_add(*source)
}

#[unsafe(no_mangle)]
#[inline(never)]
pub unsafe extern "C" fn topic42_raw_contract(
    destination: *mut u64,
    source: *const u64,
) -> u64 {
    unsafe {
        let first = source.read();
        destination.write(first.wrapping_add(1));
        first.wrapping_add(source.read())
    }
}
```

For distinct inputs with source value 7, both calls store 8 and return 14. If
the raw pointers are identical, the store changes the second read, so the raw
call stores 8 and returns 15. Constructing overlapping Rust references is not a
valid negative test; the reference contract already forbids that call.

For the optimized LLVM intermediate representation retained by this round, the
reference body's static memory-operation count is:

`C_reference = L + S + A`

`L` is one source load, `S` is one destination store, and `A` is the arithmetic.
For the distinct example, this is `1 load + 1 store + additions`.

The retained raw-pointer body contains:

`C_raw = 2L + S + A`

Substituting the same example gives `2 loads + 1 store + additions`. The
difference is `C_raw - C_reference = L`, one source load in these retained LLVM
bodies. Every conforming lowering must preserve the two functions' observable
results, but it need not use these instruction counts. This model does not
predict elapsed time. Compiler version, optimization, inlining, register
allocation, instruction selection, and surrounding code can change the final
cost.

Strict Provenance address movement also needs an ordinary bounds proof. Assume
the address arithmetic does not overflow. For element index `i`, element size
`s`, and array length `n`, the byte displacement is `d = i * s`, and a full
element read requires `i < n` and
`d + s <= n * s`. The example uses `i = 2`, `s = 8`, and `n = 4`, so
`d = 2 * 8 = 16` and `16 + 8 = 24 <= 4 * 8 = 32`. In plain language, the
third eight-byte value lies completely inside the live 32-byte array.

## What the executable material proves

Run the deterministic example:

```bash
cargo run --package rust-aliasing-provenance --example provenance_demo --release
```

It performs an in-allocation Strict Provenance write, compares an
exposed-provenance reconstruction without dereferencing it, calls both
contracts with distinct objects, and calls the raw contract with exact overlap.
The tests execute only defined behavior.

The Linux experiment builds from one exact Git archive on each required host. It
runs eight fresh correctness processes and inspects optimized LLVM intermediate
representation (IR), assembly, object code, and the linked executable. LLVM IR
is the compiler's typed low-level program before final machine instructions.
The validator requires the observed reference parameters to carry LLVM
`noalias`, which records a non-overlap promise for relevant memory accesses
under LLVM's parameter-attribute rules. It requires one source load for the
reference contract, no `noalias` on the raw parameters, and two source loads
around the store for the raw contract.

These are observations of the recorded rustc, LLVM, flags, source, and hosts.
Native output cannot prove that arbitrary Rust source obeys its aliasing or
provenance contract. The experiment reports no timing because constant-size
correctness and generated-code inspection answer the lesson's question; elapsed
startup noise would not.

## Common failures and misleading shortcuts

- **“A pointer is just an integer.”** Equal address bits do not establish the
  same allocation identity, lifetime, or access permission.
- **“`unsafe` turns the rules off.”** It moves the proof obligation to the
  programmer and the surrounding safe abstraction.
- **“Raw pointers may alias, so every raw access is valid.”** Raw pointers can
  express overlap, but each load and store still needs validity, provenance,
  alignment, initialization, and race safety.
- **“`NonNull<T>` is a valid object.”** It proves only non-null representation;
  the pointee may be dangling, misaligned, uninitialized, or inaccessible.
- **“Integer round-tripping proves a dereference.”** Address equality is only a
  numerical observation. Prefer a pointer carrier and `with_addr` when one
  exists.
- **“Wrapping pointer arithmetic permits wrapping access.”** Calculating an
  address and dereferencing it have different rules. The eventual access must
  still be valid.
- **“`&mut` means unique address bits for its whole lexical scope.”** Derived
  reborrows are normal. The rule concerns overlapping active access, not
  permanently unique bits.
- **“`UnsafeCell` removes aliasing rules.”** It permits mutation of its contents
  through shared access. It does not permit invalid `&mut` overlap or data
  races.
- **“Miri success proves the program.”** Miri is an interpreter for Rust's
  Mid-level Intermediate Representation (MIR). It checks executed paths under
  an experimental alias model and configuration. Unexecuted paths and other
  models remain outside that result.
- **“References are always faster.”** Their stronger contract can enable
  optimization, as this small function demonstrates. Real performance still
  depends on whether the workload and generated code use that opportunity.

## Practical selection guide

1. Express ownership and disjointness with safe references first.
2. Use slice-splitting APIs when the problem is two regions of one allocation.
3. Keep a real pointer as the carrier and use Strict Provenance operations for
   address manipulation within its allocation.
4. Use Exposed Provenance only at a boundary that truly erases the carrier.
   Keep that boundary small and document why reconstruction is necessary.
5. Use raw pointers behind the smallest safe abstraction that can state and
   test the complete access contract.
6. Use `UnsafeCell` only for intentional interior mutability, then add the
   synchronization or single-threaded invariant it needs.
7. Use indices or versioned handles when memory can relocate or outlive one
   address space.
8. Inspect LLVM IR when a decision depends on optimizer alias assumptions, and
   inspect final machine code when it depends on host instructions. Treat both
   as exact-build evidence.

The central rule is simple: preserve both the room number and the keycard.
Addresses locate bytes; provenance, lifetime, aliasing, and synchronization
decide whether accessing those bytes is permitted.

## Sources

Primary language, compiler, tool, and research sources are collected in
[`references.md`](references.md).
