# BPF internals

BPF is the standardized name for a kernel execution environment; eBPF is the
common name for its modern form. RFC 9669 treats both as standalone names, not
acronyms. A BPF program can run near a Linux kernel event without adding a
kernel module. The short program is only one part of the system. Permission,
verification, attachment, state, output, generated code, and lifetime are
separate contracts. A program that passes the verifier can still count the
wrong event, overload a shared map, lose output, or detach when its last owning
attachment reference disappears.

This topic uses a parcel-sorting station as a running example. A packet is a
parcel. A hook is the station where Linux calls a program. The verifier is the
safety inspector. A just-in-time (JIT) compiler translates the approved rule
card into the current processor's native instructions. Maps are storage
cabinets, helpers are approved kernel services, and a link keeps the rule card
attached to its station.

## Keep the lifecycle visible

The useful mental model is a pipeline:

1. A loader opens an eBPF object, applies relocations, creates maps, and asks the
   `bpf()` system call to load a program.
2. Linux checks permission and program-type policy before the verifier can
   provide useful program diagnostics.
3. The verifier explores reachable register and stack states. It tracks pointer
   kinds, initialized bytes, value ranges, references, and branch refinements.
   Acceptance establishes the safety properties the verifier models for that
   load.
4. An accepted program may be interpreted or translated by a JIT compiler. JIT
   compilation removes bytecode dispatch; it does not remove hook, helper, map,
   contention, or export work.
5. An attachment binds the program to a hook. Open file descriptors and other
   kernel references retain objects. BPF filesystem pins can retain programs,
   maps, or links. A legacy attachment such as `SO_ATTACH_BPF` retains its
   program independently after the program file descriptor closes. BPF Type
   Format (BTF) describes types in a form the kernel and tools can inspect.
6. On each event, the hook calls the program. The program can use approved
   helpers, update maps, and publish records. The hook-specific return value
   decides what happens next.

Verifier acceptance establishes the safety properties the verifier models for
that load and passes the applicable kernel policy. It is not a proof that the
chosen hook, key, return action, sampling rule, or resource budget is correct.

## Choose the event boundary first

| Technique | Problem solved | Simple mechanism | Does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| Express Data Path (XDP) | Decide on received packets before socket delivery | A driver or generic receive path calls the program with packet bounds | Socket policy, transmit behavior, or tracing | Available context and helper set are deliberately small; driver support changes the path | Earliest receive action or accounting matters |
| Traffic Control (TC) classifier/action | Inspect or change packets in the Linux traffic-control path | An ingress or egress queueing hook calls the program | Earliest driver-level work | It runs later than native XDP and inherits traffic-control configuration | Richer packet handling or egress is required |
| Socket or control-group hook | Apply policy near an application or process group | Linux invokes a socket filter or control-group program at a defined socket operation | Driver behavior or arbitrary kernel tracing | Semantics depend on the exact program and attach type | Policy belongs to an application or group boundary |
| Tracepoint, kernel probe, or function-entry tracing | Observe kernel execution | The program runs when an instrumented event or function executes | Stable meaning for every internal symbol or structure | Kernel probes and internal function boundaries can move between kernels | Diagnosis needs a named event and its stability is acceptable |
| Linux Security Module (LSM) hook | Enforce a security decision at a security boundary | Linux calls an eBPF LSM program at an authorization hook | Network-driver action or general tracing | Return-value composition and policy order are security-sensitive | The decision is an LSM authorization decision |

The program type fixes context, helper, return-value, and attachment rules.
Moving identical-looking source between hooks can change both what it may do
and what its return value means.

## Choose state and output by ownership

A central processing unit (CPU) is one logical execution unit as Linux reports
it. Per-CPU maps partition values by those units.

| Technique | Problem solved | How it works | Does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| Shared map value with an atomic update | Several processors update one logical value | One indivisible operation changes a shared value | Cache-line ownership cost | A hot key can serialize on one cache line | A global answer is required and measured contention stays within budget |
| Map value protected by `bpf_spin_lock` | Several related fields must change together | One program invocation takes a map-value lock | Long or blocking critical sections | Contention stalls other invocations; helper restrictions apply while locked | A bounded multi-field invariant cannot be partitioned |
| Per-CPU map | Avoid shared value cache-line ownership | Linux supplies a separate value for each possible CPU | Aggregation, memory bounds, consistent snapshots, or every shared metadata path | Memory scales with possible CPUs; readers must merge values; hash and least-recently-used map metadata can remain shared | Updates are hot and delayed aggregation is acceptable |
| Ring buffer | Variable records need one globally ordered stream | Producers reserve, fill, and submit records to a shared multi-producer, single-consumer buffer | Losslessness or consumer capacity | Reservation can fail when full; an earlier slow producer can delay later committed records | Cross-CPU ordering matters and loss is explicitly counted |
| Perf event array | Existing perf-buffer consumers need per-CPU event channels | Each CPU writes to its configured perf event buffer | One global order | Per-CPU sizing, draining, and merge policy remain operational work | Tool compatibility or independent per-CPU channels matter |

A ring buffer is not a durable queue. Reserve failure is a normal overload
outcome that the program must count or otherwise expose. Per-CPU state avoids
one update hot spot, but it trades that cost for memory and read-side work.

## Use a cost model before micro-optimizing instructions

For a parcel station, separate the one-time cost of installing a rule from the
cost paid for every parcel. The total work is:

`T_total = T_setup + N * T_event`

`T_setup` is load, verify, relocate, map creation, and attachment time. `N` is
the number of events. `T_event` is the per-event path. If setup costs 12
milliseconds and six million events use the program, setup contributes two
nanoseconds per event: `12 ms / 6,000,000 = 2 ns`. If only 60 events use it,
setup contributes 200 microseconds per event: `12 ms / 60 = 200 us`. These are
illustrative numbers, not measurements. They tell you whether to optimize
steady-state work or program churn.

Split the per-event path before blaming eBPF instructions:

`T_event = T_hook + T_native + T_helpers + T_maps + T_export + T_contention`

The terms are hook entry and exit, generated native instructions, helper calls,
map work, output publication, and waiting caused by shared state. For an
illustrative 80-nanosecond event with terms `8 + 12 + 15 + 18 + 7 + 20`, the
sum is 80 nanoseconds. Removing four nanoseconds from native instructions saves
only five percent. The model directs measurement toward the largest active
term; it does not predict any particular host.

Per-CPU payload memory is approximately:

`M_payload = P_possible * K * align8(V)`

`P_possible` is the kernel's possible CPU count, `K` is the number of allocated
value slots, `V` is the value size in bytes, and `align8` rounds up to an
eight-byte boundary. With 64 possible CPUs, one value slot, and an eight-byte counter, the payload is
`64 * 1 * 8 = 512` bytes. Map metadata and allocator overhead are extra. Use
possible CPUs, not today's online count, when setting the memory budget. A
per-CPU array and a preallocated per-CPU hash provision `max_entries` slots; a
no-preallocation hash allocates values as keys are inserted. The map type
therefore determines whether `K` is capacity or the current populated count.

A ring-buffer record uses an eight-byte header plus an eight-byte-aligned
payload. A 56-byte payload therefore occupies `align8(56 + 8) = 64` bytes. If
producers publish two million such records per second, they offer 128 million
bytes per second. A consumer draining 100 million bytes per second falls behind
by 28 million bytes per second. An eight-mebibyte buffer then fills in about
`8,388,608 / 28,000,000 = 0.30` seconds. This is a capacity calculation, not a
promise about kernel timing.

## What the executable material proves

The Rust crate contains a small, explicit model. It checks branch targets in a
tiny instruction subset and calculates the cost and capacity equations above.
It does not implement or replace the Linux verifier. Run it with:

```bash
cargo run --package ebpf-internals --example cost-and-control
```

The Linux experiment uses the raw `bpf()` system call and the kernel's
user-space application programming interface (UAPI) headers. It submits an
invalid jump, an accept-all socket filter, and a drop-all socket filter. Under the required
privileged policy it then attaches each valid program to a loopback User
Datagram Protocol (UDP) socket, checks packet behavior, retrieves translated
and JIT-compiled bytes through `BPF_OBJ_GET_INFO_BY_FD`, and disassembles the
native bytes. A 250-millisecond receive timeout is a correctness threshold, not
a latency sample.

This focused experiment proves only the observed permission, verifier,
translation, attachment, and socket-action contracts for the named kernels.
It does not measure XDP, TC, tracing, LSM, map contention, output throughput,
startup cost, or production packet rate. No elapsed-time comparison is
justified.

The retained [cross-host comparison](measurements/2026-08-19-comparison.md)
binds the result to source commit `f32d0dbfcc146bc0fb2d8739c2da668a95d95bd9`.
Both hosts passed eight fresh privileged processes. They returned the same two
16-byte translated BPF programs, but the visible native JIT bodies differed:
64 bytes for both programs on the measured AArch64 host, and 21 bytes for
accept versus 16 bytes for drop on the measured x86-64 host. This is generated-
code evidence for two named kernels, not an architecture-family ranking.

## Common failures and misleading shortcuts

- **“Verified means correct.”** The verifier admits safe, policy-compliant
  execution. It cannot know the intended event, key, action, or business rule.
- **“JIT means free.”** Translation removes interpreter dispatch. Hook entry,
  helpers, maps, cache-line movement, output, and the generated instructions
  remain.
- **“Per-CPU means synchronization-free.”** Updates are partitioned. Readers
  still need a merge rule and must define snapshot consistency.
- **“The ring buffer is lossless.”** Reservation can fail at capacity, and a
  producer holding an earlier reservation can delay visibility of later data.
- **“Compile Once, Run Everywhere means every kernel.”** Compile Once, Run
  Everywhere (CO-RE) uses BTF relocations to adapt supported field layouts. It
  cannot create a missing hook, helper, type, permission, or semantic contract.
- **“The verifier rejects every loop.”** Modern kernels accept loops whose
  bounds and state exploration meet the verifier's rules. Large ranges can
  still cause excessive verification work.
- **“One instruction limit applies to every program.”** Limits and admission
  policy depend on privilege, kernel version, program type, and verifier
  complexity. Record the exact rejection instead of relying on a slogan.
- **“A kernel version proves a feature is usable.”** Configuration, permission,
  lockdown, attach target, driver support, and helper availability also matter.
- **“A test-run result proves the normal hook path.”** `BPF_PROG_RUN` explicitly
  executes a loaded program with supplied context. It is useful for focused
  correctness checks, but it does not exercise normal attachment, driver work,
  contention, or event arrival.
- **“Pinning makes an object permanent.”** Pinning keeps a kernel object alive
  across loader exit. It does not survive reboot, clean stale objects, or prove
  that the intended link is attached.

## Practical selection guide

1. Pick the hook whose context and action match the decision. Do not begin with
   a favorite program type.
2. Define permission and feature probes for the deployed kernel and attach
   target. On Linux 6.12, `kernel.unprivileged_bpf_disabled=1` disables
   unprivileged calls and cannot be changed back to zero; value `2` is an
   administrator-reversible disabled state.
3. Partition hot updates with per-CPU maps when merge semantics and memory
   bounds are acceptable. Use shared atomics or a short lock only when a global
   invariant requires them.
4. Use a ring buffer when one ordered stream matters, and budget loss counters,
   consumer bandwidth, and stalled reservations. Use a perf event array when
   per-CPU channels or existing tooling matter more.
5. Prefer a loader based on libbpf and CO-RE when BTF is available and the
   relocation boundary is explicit. Use the raw system call for minimal tests
   and debugging, not as an excuse to rebuild lifecycle management poorly.
6. Keep program, map, link, and pin ownership explicit. Test loader crash,
   replacement, and cleanup paths.
7. Measure the complete active hook on the real workload. Treat instruction
   counts, test-run results, and isolated map benchmarks as narrower evidence.

The central rule is simple: an eBPF program is a managed kernel object in a
hook-specific runtime, not just a short list of instructions. Correct systems
work keeps admission, semantics, state, output, generated code, and lifetime
separate, then measures the complete path that matters.

## Sources

Primary sources and the Linux 6.12 boundary are collected in
[`references.md`](references.md).
