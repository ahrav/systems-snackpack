# Compiler optimization boundaries

An optimization crosses a boundary only when all of these gates permit it:

1. The transformation preserves the language and target semantics.
2. The optimizer can see the body, values, and relevant effects.
3. Alias and escape facts justify motion or elimination.
4. Symbol binding permits the observed definition to replace the call.
5. A useful pass runs while those facts coexist.
6. The target cost model judges the transformation profitable.

Inlining, link-time optimization, and stronger effect contracts change
different gates. None is a general-purpose “optimization on” switch.

## Focused boundary

The example keeps the computation fixed and changes body visibility:

- `local`: an inlineable helper in the binary crate;
- `imported`: `#[inline(always)]` in a dependency crate;
- `opaque`: an ordinary exported dependency function, with LTO disabled.

The experiment checks correctness, measures fresh processes in balanced `AB`
and `BA` pairs, and inspects the final linked image. A retained call identifies
a boundary in this exact build. It does not prove that the attribute is a
language-level barrier or that call overhead alone explains a timing change.

```bash
cargo build --release \
  -p compiler-optimization-boundaries \
  --example boundary_probe

topics/016-compiler-optimization-boundaries/experiment/run_processes.sh \
  target/release/examples/boundary_probe \
  /tmp/topic16-raw.csv \
  /tmp/topic16-summary.csv
```

The timed region excludes process launch, allocation, input generation, and
one untimed warm-up. Each CSV row remains a process observation; loop rounds
inside one process are subsamples, not independent replicates.

See the [first-round decision record](rounds/01.md), [measurement
contract](measurements/README.md), and [primary sources](references.md).
