# Topic 44 measurement contract

This topic retains deterministic correctness and generated-code evidence. It
does not report elapsed time. Eight independently launched processes per host
must reproduce the exact counterexample, valid equal-schema merge, and two
rejection controls.

The host runner records source, binary, host, CPU, kernel, toolchain, build flag,
output, LLVM intermediate representation, assembly, object, symbol, and
disassembly receipts. The code-generation files describe only the named source,
compiler, flags, and machine. They do not establish a performance or
instruction-set-family claim.

The first retained run's host and cross-host notes will link the sealed raw
receipts after both required Linux targets pass the validation contract in
[`../rounds/01.md`](../rounds/01.md).
