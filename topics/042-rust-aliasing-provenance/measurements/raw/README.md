# Raw evidence

Each source-binding directory retains the runtime `xxl` resolution, sealed Arm
and x86 host-result archives, source identity, local validation output, and a
SHA-256 digest manifest.

The Git archive itself is not retained, because it contains the full workspace
including earlier topics' raw evidence. Each bundle instead binds its input by
commit and archive digest, both recorded in its `SOURCE.md` and checked by the
validator, so the archive can be regenerated from the named commit and matched
against the recorded digest.

The host bundles contain eight fresh process streams, host and toolchain
metadata, all seven workspace gate logs, optimized LLVM intermediate
representation, assembly, object code, executable metadata and disassembly,
and an independent validator receipt. They contain no timing samples.
