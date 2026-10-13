# Measurement contract

Freeze: 4 candidates (`mod`, `hrw`, `ring1`, `ring64`), node counts8/64/256,
128-key small batches,32768 uniform keys,32768 accesses with95% to one key.
Fixed noncryptographic mix; prehashed input; no hostile-input hash claim.
Six process blocks alternate forward/reverse order. One separate warmup process
per candidate/cell, then one untimed input pass in each measured process.
216 measured and36 warmup processes per campaign. Inner iterations are not samples.

Steady boundary:262144 lookups, wrapping checksum and black_box, excluding input,
map construction, output and destruction. Cold boundary:map allocation/build plus
one first pass; excludes key preparation, drop, process startup. Cold means first
pass, not cache eviction. No affinity or power-state control on local macOS.
Heap payload includes vector capacities only, excluding allocator overhead/struct.

Winner: candidate at least5% faster than EVERY eligible rival in ALL6 paired blocks.
Otherwise unresolved. Report all4 candidates and separate HRW/ring64 comparison.
The latter is a declared alternative set, not a proven balance threshold:64 tokens
still show finite-map skew. Report ranges and medians. Do not rerun to seek winners.

Correctness uses linear successor versus binary search, score sorting versus HRW
scan, quotient/remainder identity versus modulo, token boundary/wrap/empty/duplicate
cases, input-order invariance, strict add/remove locality, and full-period modulo
counts. Shared hash semantics are deliberately fixed; this does not prove hash quality.
Movement counts65536 keys at8nodes with add8, remove3, replace3with8. Byte weighting
is adversarial and candidate-relative:old-owner3 objects1024units, others1. Request
weight65536 for key0, otherwise1. These distributions expose accounting boundaries;
they are not a cross-candidate physical byte-volume comparison.

Required Linux hosts:dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com and runtime-resolved
xxl. Both rejected expired Midway authentication before remote identity/transfer;
one bounded retry each also rejected. Exact-source Linux runs remain pending.
Local AppleM1Pro evidence is not Linux/ISA-wide or production migration evidence.
