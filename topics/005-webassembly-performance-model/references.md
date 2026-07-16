# References

- [WebAssembly Core 3.0](https://webassembly.github.io/spec/core/) — Current core syntax, validation, instantiation, and execution semantics.
- [V8 Wasm compilation pipeline](https://v8.dev/docs/wasm-compilation-pipeline) — Liftoff, TurboFan, tiering, and the lack of on-stack replacement.
- [V8 speculative Wasm optimizations](https://v8.dev/blog/wasm-speculative-optimizations) — Chrome M137 guarded indirect-call inlining and its benchmark scope.
- [Wasmtime 46.0.1 fast execution](https://github.com/bytecodealliance/wasmtime/blob/v46.0.1/docs/examples-fast-execution.md) — Cranelift, target features, reservations, guards, and bounds-check elimination.
- [Wasmtime 46.0.1 fast compilation](https://github.com/bytecodealliance/wasmtime/blob/v46.0.1/docs/examples-fast-compilation.md) — Winch, parallel compilation, and cache tradeoffs.
- [Wasmtime 46.0.1 fast instantiation](https://github.com/bytecodealliance/wasmtime/blob/v46.0.1/docs/examples-fast-instantiation.md) — Pooling, copy-on-write images, and reusable pre-instantiation.
- [Wasmtime 46.0.1 precompilation](https://github.com/bytecodealliance/wasmtime/blob/v46.0.1/docs/examples-pre-compiling-wasm.md) — Artifact compatibility and trust boundary.
- [Wasmtime 46.0.1 platform support](https://github.com/bytecodealliance/wasmtime/blob/v46.0.1/docs/stability-platform-support.md) — Cranelift, Winch, Pulley, just-in-time, and ahead-of-time boundaries.
- [Component Model Canonical ABI](https://github.com/WebAssembly/component-model/blob/main/design/mvp/CanonicalABI.md) — Rich-value lifting and lowering semantics.
- [Rust `wasm32-unknown-unknown`](https://doc.rust-lang.org/stable/rustc/platform-support/wasm32-unknown-unknown.html) — Rust and LLVM feature baseline.
- [Relaxed SIMD proposal](https://github.com/WebAssembly/relaxed-simd/blob/main/proposals/relaxed-simd/Overview.md) — Permitted implementation-dependent SIMD choices.
- [Haas et al., PLDI 2017](https://doi.org/10.1145/3062341.3062363) — Original design and historical performance evaluation; not a current multiplier.
