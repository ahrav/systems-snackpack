# Primary sources and version boundaries

The executable crate has a minimum supported Rust version of 1.93 because that
is the workspace toolchain boundary. Rust stabilized the Strict Provenance APIs
used here in 1.84. The retained Linux notes record the exact rustc and LLVM
versions used for code generation. Rust's exact general aliasing model remains
under specification, so these notes do not turn current compiler output or an
experimental interpreter model into a permanent language guarantee.

## Rust pointer and reference contracts

- [Rust standard library: pointer provenance](https://doc.rust-lang.org/std/ptr/index.html#provenance)
  defines the abstract provenance model used by the pointer APIs and separates
  Strict Provenance from Exposed Provenance.
- [Rust primitive pointer methods](https://doc.rust-lang.org/core/primitive.pointer.html)
  define `addr`, `with_addr`, `map_addr`, `expose_provenance`, pointer
  arithmetic, and their safety boundaries. Availability and exact text follow
  the selected standard-library release.
- [Rust standard library: Exposed Provenance](https://doc.rust-lang.org/std/ptr/index.html#exposed-provenance)
  describes integer exposure and the less precise global recovery mechanism.
- [`with_exposed_provenance`](https://doc.rust-lang.org/std/ptr/fn.with_exposed_provenance.html)
  documents the reconstruction operation and recommends Strict Provenance APIs
  when possible.
- [Rust Reference: behavior considered undefined](https://doc.rust-lang.org/stable/reference/behavior-considered-undefined.html)
  lists invalid pointer access, aliasing, data races, invalid values, and other
  undefined behavior. The aliasing rules are explicitly not yet exact.
- [Rust pointer-to-reference conversion](https://doc.rust-lang.org/std/ptr/index.html#pointer-to-reference-conversion)
  summarizes the additional validity and aliasing obligations when a raw
  pointer becomes a reference.
- [Rust Reference: raw borrow operators](https://doc.rust-lang.org/reference/expressions/operator-expr.html#raw-borrow-operators)
  shows how `&raw const` and `&raw mut` create raw pointers without first
  creating a possibly invalid reference.
- [`UnsafeCell<T>`](https://doc.rust-lang.org/std/cell/struct.UnsafeCell.html)
  defines the shared-immutability exception and states what it does not relax.
- [`NonNull<T>`](https://doc.rust-lang.org/std/ptr/struct.NonNull.html)
  defines the non-null raw-pointer wrapper, covariance, and null-pointer
  optimization boundary.

## Compiler and checking boundaries

- [LLVM Language Reference: parameter attributes](https://llvm.org/docs/LangRef.html#parameter-attributes)
  defines `noalias`, `readonly`, and `writeonly` at the LLVM intermediate-
  representation boundary. These attributes are compiler output, not source-
  language proof by themselves.
- [rustc command-line arguments](https://doc.rust-lang.org/rustc/command-line-arguments.html)
  defines `--emit` outputs used to retain LLVM IR, assembly, and object code.
- [Miri](https://github.com/rust-lang/miri/)
  documents the Rust Mid-level Intermediate Representation interpreter,
  supported checks, Strict Provenance flag, experimental alias models, and the
  limits of a dynamic executed-path check.
- [Stacked Borrows working model](https://github.com/rust-lang/unsafe-code-guidelines/blob/master/wip/stacked-borrows.md)
  describes one experimental operational alias model. It is not the final Rust
  specification.

## Research boundary

- [Stacked Borrows: An Aliasing Model for Rust](https://doi.org/10.1145/3371109)
  gives the formal research model and evaluation behind Stacked Borrows.
- [Tree Borrows](https://doi.org/10.1145/3735592)
  presents a related experimental model with different retagging and access
  rules. The paper supports comparing models; it does not make either one the
  final Rust specification.
