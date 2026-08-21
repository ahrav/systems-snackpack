# Cross-host comparison: 2026-08-20

Both required hosts replayed the same commit-bound archive and passed the same
package gates, eight fresh-process checks, receipt validation, and generated-code
inspection.

| Observation | Arm host | Runtime-resolved `xxl` host |
| --- | ---: | ---: |
| Architecture | `aarch64` | `x86_64` |
| rustc | 1.95.0 | 1.97.1 |
| Large future | 4,099 bytes | 4,099 bytes |
| Small future | 16 bytes | 16 bytes |
| `YieldOnce::poll` | 56 bytes | 28 bytes |
| `SafeTake::poll` | 180 bytes | 151 bytes |
| `UnsafeTake::poll` | 208 bytes | 195 bytes |
| Fresh processes | 8 | 8 |
| Timing | not measured | not measured |

The matching future sizes and state outcomes are measured facts. The MIR on
both hosts explains the size difference by which user value survives the
suspension: a 4,096-byte array versus a `u64` checksum. That explanation is an
inference from the retained compiler representation, not a stable layout rule.

The native symbol sizes differ. Compiler versions, target instruction sets,
link layout, and generated instructions also differ, so this experiment cannot
attribute the difference to one cause or generalize it to either instruction-set
architecture. A timing comparison would be misleading because the probe uses a
manual driver rather than production executor and scheduler paths.
