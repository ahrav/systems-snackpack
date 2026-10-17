# Primary sources

Retrieved 2026-10-17. Compiler behavior in this experiment is pinned to Rust 1.93.1.

- [Rust compiler development guide: monomorphization](https://rustc-dev-guide.rust-lang.org/backend/monomorph.html): collection of concrete instances and codegen-unit placement.
- [Rust Reference: codegen attributes](https://doc.rust-lang.org/reference/attributes/codegen.html#the-inline-attribute): every inline attribute is a hint the compiler may ignore.
- [Rust Reference: trait objects](https://doc.rust-lang.org/reference/types/trait-object.html): value/vtable representation and dynamic dispatch semantics.
- [Cargo profiles](https://doc.rust-lang.org/cargo/reference/profiles.html): optimization, LTO, codegen units, panic strategy, debug and strip settings.
- [Rust compiler codegen options](https://doc.rust-lang.org/rustc/codegen-options/index.html): exact direct-rustc flags used by the campaign.
- [std::hint::black_box](https://doc.rust-lang.org/std/hint/fn.black_box.html): best-effort optimization barrier; verify generated code separately.
- [GNU size](https://sourceware.org/binutils/docs/binutils/size.html): section-level versus aggregate size reporting.
