# Primary sources

Read 2026-10-18. Reference and standard-library web pages track current Rust; the experiment is pinned to Rust 1.93.1. APIs used by the example exist in that toolchain.

- [Trait objects](https://doc.rust-lang.org/reference/types/trait-object.html): erased data and virtual method table.
- [Option representation](https://doc.rust-lang.org/std/option/index.html#representation): the documented NonZero layout guarantee.
- [Type layout](https://doc.rust-lang.org/reference/type-layout.html): representation boundaries.
- [Destructors](https://doc.rust-lang.org/reference/destructors.html): live values, local and field destruction order.
- [Panic](https://doc.rust-lang.org/reference/panic.html): unwind and abort.
- [catch_unwind](https://doc.rust-lang.org/std/panic/fn.catch_unwind.html): catches unwinding, payload and invariant limits.
- [Send and Sync](https://doc.rust-lang.org/nomicon/send-and-sync.html): ownership transfer and reference sharing.
- [Slices](https://doc.rust-lang.org/std/primitive.slice.html): indexing and unchecked-reference requirements.
- [Iterator::zip](https://doc.rust-lang.org/std/iter/trait.Iterator.html#method.zip): shorter-input termination.
- [black_box](https://doc.rust-lang.org/std/hint/fn.black_box.html): best-effort optimization barrier.
