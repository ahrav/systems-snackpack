# Topic 5: WebAssembly performance model

A WebAssembly module has no fixed, format-wide performance multiplier. Model
end-to-end cost from module readiness, guest code, runtime services, and host
or component boundaries. Measure each term for the selected engine,
configuration, workload, and target.

## Cost model

A module becomes callable after transfer, decode, validation, compilation,
linking, instantiation, start work, and any lazy first-call compilation. A code
cache replaces compilation with lookup, compatibility checks, mapping, and
relocation; it does not eliminate readiness work.

```text
T_first_request = T_ready + T_steady_request
T_steady_request = T_guest + T_runtime + T_boundary

T_guest_loop(N) = B_export + N * G
T_host_loop(N) = B_export + N * (B_import + H)
C_added(N) = (T_host_loop(N) - T_guest_loop(N)) / N
```

`B_export` is one C-to-Wasm export call. `G` is one in-guest step.
`B_import + H` is one imported C callback and its arithmetic. The added cost
includes the import trampoline, runtime state, value handling, host
implementation, and code-generation differences. It is not a pure transition
latency.

These terms are accounting categories. Engines can overlap readiness phases,
so measure the critical path instead of summing overlapping wall times.

## Technique boundaries

| Choice | Benefit | Cost or limit |
|---|---|---|
| Interpreter | Avoids native-code compilation | Dispatches each operation at run time |
| Baseline compiler | Uses a short native-code pipeline | Runs fewer optimization and allocation passes |
| Optimizing compiler | Applies more optimization and register allocation | Adds compile latency, compiler CPU, and code memory |
| Tiering | Starts with baseline code and recompiles hot functions | Adds profiling and warmup state; current calls may remain baseline |
| Precompiled artifact | Moves compilation before deployment | Couples the artifact to engine, configuration, target, and trust policy |

Ahead-of-time (AOT) describes when compilation runs, not optimizer quality. V8
moves hot functions from Liftoff to TurboFan, but it does not perform on-stack
replacement: a call already running in Liftoff finishes there. Wasmtime 46.0.1
lets an embedder select Winch or Cranelift, but one module stays entirely on the
selected compiler.

Wasmtime 46.0.1 can omit explicit bounds checks for a 32-bit linear memory on a
64-bit host when signals-based traps are enabled, the reservation covers 4 GiB,
and the guard covers the instruction's static offset. Smaller reservations,
64-bit linear memories, and smaller guards do not satisfy that proof; the
compiler emits any checks that remain necessary. Reserved virtual address
space is not resident memory.

Compilers can inline direct calls. `call_indirect` enforces table bounds, null,
and type checks, although a profiling engine can guard and inline a stable
target. Core imports cross an embedding boundary. The Component Model Canonical
ABI converts component values to core values and linear-memory
representations; strings and lists can require allocation and copying.

Core single instruction, multiple data (SIMD) operations use portable 128-bit
values; they do not guarantee a native-width mapping or a lane-count speedup.
Measure lowering expansion, tail handling, floating-point semantics, and memory
bandwidth. Wasmtime validates configured features before compilation, so an
unsupported instruction rejects a module even if its function is never called.

## Focused experiment

[`experiment/boundary.wat`](experiment/boundary.wat) exports `guest_loop` and
`host_loop`. Both run the same dependency-chained wrapping multiply-add for
`N` steps. `guest_loop` calls a Wasm function; `host_loop` calls one typed C
import per step. Each measured process invokes each export once after warmup,
so both paths include one C-to-Wasm call.

The C embedder timestamps WAT file loading, WAT decoding, engine creation,
validation, compilation, store and import setup, instantiation, export lookup,
internal warmup, and the two measured calls. `cold_ready_ns` spans process entry
through export lookup; it is a harness-specific readiness measurement, not an
application startup result.

Run the independent Rust digest check:

```bash
cargo run -p systems-snackpack-topic-005 --example check_digest
```

On 64-bit Linux with Bash, GCC, Python 3, `taskset`, `curl`, `sha256sum`, and
`xz`, run from the repository root:

```bash
cd topics/005-webassembly-performance-model/experiment
./bootstrap.sh
./run_all.sh
```

The scripts verify the Wasmtime 46.0.1 release archives by SHA-256 and configure
Cranelift with speed optimization and parallel compilation disabled. By
default, they use `/tmp/systems-snackpack-topic-005` and write evidence beneath
its `evidence/` directory. Set `WASM_TOPIC5_ROOT` and
`WASM_TOPIC5_EVIDENCE_DIR` to change those paths.

The runner excludes two whole-process warmups. Each child process also performs
three unmeasured internal warmup rounds of 100,000 steps per path. It then makes
one 10-million-step measured call to each path. The 12 retained processes
alternate guest-first and host-first order, six of each. The fresh process pair
forms one paired observation. The process is the replication unit; loop
iterations are subsamples.

All 24 measured process pairs passed correctness. The recorded AArch64 host had
a median paired added callback-path cost of `71.899544 ns/step`, with an exact
96.1426% sign interval of `71.075934–75.039677 ns/step`. The recorded x86-64
host had a median of `46.654221 ns/step`, with an interval of
`46.424603–47.691650 ns/step`.

These intervals cover fresh-process variation within one host, build, and time
block. They do not estimate rebuild, runtime-version, host, fleet,
instruction-set-architecture, or vendor variation. See the
[`measurements`](measurements/README.md) index and individual host records for
the method and raw evidence.

## Failure checklist

- Split startup, first call, warmed guest work, and boundary work.
- Record engine, compiler tier, features, target, and memory configuration.
- Compare equivalent optimization, allocator, input, and correctness boundaries.
- Batch fine-grained host calls unless latency or ownership requires otherwise.
- Inspect generated code; bytecode does not establish checks or instruction choice.
- Treat source-language undefined behavior as a producer-compiler problem.
- Keep fixed SIMD, relaxed SIMD, memory64, Wasm GC, WASI, and components in scope.
- Report process-level variation and each host independently.
