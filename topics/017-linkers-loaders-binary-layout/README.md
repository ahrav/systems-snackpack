# Linkers, loaders, and binary layout

The final ELF image and loader trace establish runtime behavior. Source flags,
object sections, and compiler assembly establish intent.

## Runtime model

The compiler emits sections, symbols, and relocation requests. The static linker
selects definitions, lays out addresses, emits program headers, and chooses
relocation and call forms. The kernel maps `PT_LOAD` segments. The dynamic
loader maps dependencies, applies relocations, resolves symbols, protects RELRO
pages, and runs constructors.

Sections organize link-edit data. Segments define runtime mappings. A section
change matters at runtime only through the addresses, pages, permissions,
relocations, or instructions it produces.

## Focused experiment

The glibc Linux experiment generates a shared object with 4,096 default-visible
functions and three position-independent executables:

- `lazy` uses PLT calls and `-z lazy`;
- `now` uses PLT calls and `-z now`;
- `noplt` uses `-fno-plt` and `-z now`.

The causal treatment runs the same `lazy` bytes with `LD_BIND_NOW` absent and
with `LD_BIND_NOW=1`. It separates whole-process startup, in-process first use,
and a resolved steady interval. Separately linked images provide structural
evidence only because linking changes layout as well as binding policy.

The driver removes inherited `LD_*` controls and `GLIBC_TUNABLES` from every
measured fixture process. The eager arm restores only `LD_BIND_NOW=1`.
`startup_ns` measures the parent-observed `subprocess.run` interval, including
child creation and exit.

```bash
taskset -c 0 python3 \
  topics/017-linkers-loaders-binary-layout/experiment/binding_experiment.py \
  --work-dir /tmp/topic17-build \
  --output-dir /tmp/topic17-evidence \
  --blocks 12 \
  --iterations 25000000
```

Each outcome uses 12 complete alternating `ABBA` and `BAAB` blocks. Every letter
launches a fresh process. The estimate is the geometric eager/lazy ratio from
one log contrast per block. The 95% Student-t interval covers block variation
for that host, image, workload, and run window.

The driver also runs an A/A control through the same process path. It reports
the control interval but does not enforce an acceptance threshold.

See the [first-round decision record](rounds/01.md), [measurement
contract](measurements/README.md), and [primary sources](references.md).
