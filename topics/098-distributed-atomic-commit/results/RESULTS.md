# Topic 098 results

All three hosts passed the independent abstract-specification checker and the
crate's two unit tests and one doctest. Safe state graphs have zero violations.
Both fault variants produce reachable contradictory terminal outcomes.

Tested source: `8f32345431201f2a84d826a398867e9997418d6b`.
Source archive SHA256:
`8ad1b45bdbc8748c8d59b424edf1fea1a80e2ac972950bb5c9dc12bcaae6f4ce`.
All nine archive file members were compared with Git. Both Linux transfer hashes
matched. Later commits add results only; executable and checker bytes stay fixed.

| Model | Participants | States | Transitions | Disagreement states | States with a path to uniform completion |
|---|---:|---:|---:|---:|---:|
| Safe | 2 | 187 | 702 | 0 | 187 |
| Safe | 3 | 1,279 | 6,861 | 0 | 1,279 |
| Timeout abort fault | 2 | 295 | 1,270 | 20 | 275 |
| COMMIT before persistence fault | 2 | 488 | 2,073 | 40 | 406 |

Counts are exhaustive within this finite transition system. They are neither
failure probabilities nor independent experimental trials. Graphs match byte for
byte across hosts. Safe totals are 1,466 states and 7,563 transitions per host.

## Counterexamples

The shortest discovered timeout trace is eight transitions: A prepares and votes,
then times out and aborts; B prepares and votes; the coordinator persists COMMIT
using its retained votes, sends it to B, and B commits. A's earlier YES became
false when A unilaterally aborted. The transfer ends at (100, 10).

The early-COMMIT trace is eleven transitions: both prepare and vote; the
coordinator chooses volatile COMMIT, sends it to A, and A commits; the coordinator
crashes and loses that choice; recovery persists ABORT; B receives ABORT and
aborts. The transfer ends at (90, 0). The per-host JSON includes every step.

Terminal records stay stable even in the fault models. Rejecting contradictory
late messages locally cannot repair an already split global decision.

## Hosts and commands

- Local macOS 26.7.2 arm64, Python 3.13.16.
- dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com: Linux aarch64, CPU implementer
  0x41 / part 0xd40, kernel 6.12.113-138.209.amzn2023, Python 3.9.25.
- xxl: verified Linux x86_64, Intel Xeon Platinum 8488C, same kernel release,
  Python 3.9.25.
- All hosts: Rust 1.93.1, LLVM 21.1.8, default debug build, no external dependencies.

Each host extracted the same committed archive into task-specific scratch and ran:

```bash
python3 topics/098-distributed-atomic-commit/experiment/run.py /tmp/topic098-results 8f32345431201f2a84d826a398867e9997418d6b
```

The runner records versions, tests, graphs, oracle output and SHA256 hashes.
Full graphs, CPU metadata, source archive, standalone lesson, and inspected visual
are retained in the daily chat's Topic098 output bundle. The source archive also
contains the root Cargo manifests and toolchain file for independent replay.

## Scope

This is a correctness model with atomic durable transitions. Physical persistence,
network recovery latency, locks, read isolation, and database throughput remain
unmeasured. Participant downtime, storage corruption, multiple transaction IDs,
log reclamation, dynamic membership, and competing coordinators are excluded.
The completion-path result is existential. Fairness-dependent liveness remains
unproved. The Python checker independently checks the abstract relation; the Rust
explorer defines which concrete transitions exist.

No performance winner is claimed. Protocol message and delay formulas in the
README are derived estimates under their stated assumptions.

## Repository validation

All six workspace checks passed: formatting, Clippy with warnings denied,
unit/bin/example tests, doctests, benchmark compilation, and rustdoc with warnings
denied. Full workspace counts: 542 unit/bin/example tests and 156 doctests.
No benchmark timing was collected. Hooks remained enabled throughout.
