# Topic 44 measurement contract

This topic retains deterministic correctness and generated-code evidence. It
does not report elapsed time. On each host, eight independently launched
processes must reproduce the exact counterexample, valid equal-schema merge,
and two rejection controls.

The host runner records source, binary, host, CPU, kernel, toolchain, build flag,
output, LLVM intermediate representation, assembly, object, symbol, and
disassembly receipts. The code-generation files describe only the named source,
compiler, flags, and machine. They do not establish a performance or
instruction-set-family claim.

The first retained run passed the validation contract in
[`../rounds/01.md`](../rounds/01.md). Each required host passed all eight fresh
processes and the receipt validator. The retained notes are:

- [`2026-08-23-arm.md`](2026-08-23-arm.md)
- [`2026-08-23-xxl.md`](2026-08-23-xxl.md)
- [`2026-08-23-comparison.md`](2026-08-23-comparison.md)

The sealed bundles and scoped source archive are under
[`raw/2026-08-23-b8d0c8b/`](raw/2026-08-23-b8d0c8b/).
