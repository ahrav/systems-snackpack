# Measurement contract and boundaries

Six cells: 8 ordered once, 8 shuffled four copies, 1024 reversed once,
1024 shuffled four copies, 10000 ordered once, 10000 shuffled four copies.
Three candidates: copy/sort, BTreeMap, dense slots. Each cell uses all six
candidate permutations as six paired process blocks. One extra warmup process
per candidate/cell; each measured process also performs 20 warmup iterations.
A process times a fixed batch of complete normalizations. Inner iterations are
not independent samples. All input generation and independent oracle work occur
outside the timer; allocation, validation, normalization, output, and drop occur
inside. Process startup, compilation, network, payload I/O, durable journals and
cold-cache behavior are excluded. Linux runs pin to the first allowed CPU;
macOS has no affinity control in this runner. No separate A/A calibration.

Select a candidate only if its time is <=0.95 times every rival in every paired
block. Otherwise report unresolved. Report medians and observed min/max, not a
confidence interval. Fixed seeded shuffling and native default release flags.
No CPU counter or candidate-only assembly-based causal claim.

The independent scanning oracle exhaustively checks 19,531 streams of length
zero through six over five tokens. Maximum count and 28 observation/identity
pairs are covered. These tests validate the local model, not AWS behavior.

## Required Linux evidence is pending

On 2026-10-10, both prescribed hosts failed two bounded authentication attempts:
Arm dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com and runtime-resolved xxl,
dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com. WSSH reports expired/invalid
Midway authentication. No current hostname, architecture, kernel, compiler or
Linux result was obtained. Alias resolution is not architecture verification.
Replay exact committed source and runner after authentication is restored;
verify architecture before execution and retain source/runner hashes and host
metadata. Do not claim an Arm Linux or x86 winner from local macOS evidence.

Initial and committed-source local campaigns are retained separately. The final
compact receipt records exact source identity, results, and external raw paths.
