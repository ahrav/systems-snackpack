# NUMA first-touch placement and migration

A thread can move to a different CPU while its pages stay attached to the
memory node that first allocated them. On a non-uniform memory access (NUMA)
machine, those remote accesses cross a socket or node interconnect. Keeping the
thread in place may waste access time, but moving or copying the pages has an
up-front cost. The right choice depends on placement, workload lifetime, read
and write mix, and measured costs on the exact machine.

## Terms and mechanism

- A **NUMA node** is a set of CPUs and memory with a locality relationship.
  Node identifiers and distance values describe topology; distance is not a
  latency measurement.
- **First touch** is shorthand for demand allocation under the faulting
  thread's memory policy. This experiment writes one 64-bit next-page index in
  every anonymous page while pinned, so the write fault materializes the page.
  A read-only first access can have different anonymous-memory behavior.
- An access is **local** when the worker CPU and observed page are on the same
  node and **remote** when their node identifiers differ.
- **CPU affinity** restricts where a thread may execute. **Memory policy** and
  cpuset memory-node constraints govern where allocation may occur. Setting one
  does not imply the other.
- **Migration** moves existing pages. **Replication** retains another copy and
  therefore adds capacity and consistency costs.
- Linux **automatic NUMA balancing** samples accesses and may move tasks or
  pages. Its state is part of the experiment, not background trivia.

For anonymous pages in this experiment, the causal sequence is:

```text
faulting CPU + memory policy + allowed nodes
                    |
                    v
             initial page node
                    |
       worker CPU + observed page node
                    |
                    v
              local or remote
```

Page placement can later change because of an explicit migration, policy
operation, automatic NUMA balancing, or process behavior. Record it before and
after the measured phase.

## Technique comparison

| Technique | Best fit | Cost or failure mode | Evidence required |
|---|---|---|---|
| Serial first touch | One stable owner | A later thread move leaves pages remote | Faulting CPU, policy, per-page placement |
| Parallel first touch | Stable partitioned ownership | Work partition and touch partition can drift | Worker-to-range mapping and placement |
| Bind or preferred policy | Deliberate allocation node | Binding can fail; preferred policy can fall back | Effective policy and allowed nodes |
| Interleave | Shared streaming bandwidth or capacity | Some accesses are intentionally remote | Node distribution and bandwidth result |
| Migrate | A long-lived new owner | Copy, isolation, page-table, and disruption cost | Before/after placement and migration time |
| Replicate | Read-mostly data used on several nodes | Extra bytes and write synchronization | Replica residency, read/write mix, consistency |
| Automatic balancing | Long-lived changing locality | Sampling, convergence, and migration overhead | Kernel setting plus time-resolved placement |

None of these techniques is universally “NUMA aware.” The workload's ownership
pattern decides which placement is useful.

## Cost model

Let `A` be future accesses that would otherwise be remote, `Ll` and `Lr` the
exposed local and remote cost per access, and `Cm` the complete workload-visible
migration cost:

```text
C_keep    = A * Lr
C_migrate = Cm + A * Ll
A_migrate_break_even = Cm / (Lr - Ll), when Lr > Ll
```

For replication, let `Cr` be creation and publication cost, `W` the writes in
the decision horizon, and `Cs` the synchronization cost per write:

```text
C_replicate = Cr + W * Cs + A * Ll
A_replication_break_even = (Cr + W * Cs) / (Lr - Ll)
```

Capacity is a separate feasibility constraint because bytes cannot be added to
nanoseconds without an explicit workload-specific value. Replication also
needs a declared consistency contract.

For a mixed placement with `Al` local and `Ar` remote accesses:

```text
C_access = Al * Ll + Ar * Lr
remote_penalty = Ar * (Lr - Ll)
```

These are exposed-cost accounting identities. Concurrent misses can overlap;
streaming can become bandwidth-bound; caches, prefetching, coherence, and page
walks change what an elapsed-time benchmark observes. Do not substitute the
kernel's relative NUMA distance for `Ll` or `Lr`.

[`src/lib.rs`](src/lib.rs) implements the identities as pure functions. It also
compares keep, migrate, and optional replication totals. Exact ties retain less
placement state: keep over migrate, then migrate over replicate.

## Evidence model

Keep these claims separate:

1. **Topology:** CPU-to-node lists, online nodes, node distances, and memory
   capacity describe the host.
2. **Policy:** affinity, allowed CPU and memory-node masks, memory policy,
   automatic balancing, and huge-page state describe constraints.
3. **Placement:** a successful per-page query before and after the measured
   phase establishes where the sampled pages were observed.
4. **Mechanism:** exact source, compiler invocation, and final binary inspection
   establish the intended touch and access shape.
5. **Outcome:** fresh-process timings and process-pair contrasts establish only
   the measured workload effect in that run window.

Topology does not prove placement. Placement does not prove that traffic reached
DRAM. Assembly does not prove placement. Elapsed time does not identify the
interconnect or memory controller as the cause.

## Initial two-host observations: pre-artifact only

The following 2026-08-04 scratch observations selected the checked-in design.
They did not run the source in this directory and are not retained artifact
results. The exact checked-in candidate and its source-bound records supersede
them.

- **Arm correctness control:**
  `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, `aarch64`, kernel
  `6.12.94-123.192.amzn2023.aarch64`, exposed 64 CPUs and one NUMA node. A
  256 MiB mapping contained 65,536 pages, all observed on node 0 before and
  after. With one node there was no remote treatment and there is no remote
  timing claim.
- **Two-node x86 scratch treatment:** alias `xxl` resolved to
  `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, `x86_64`, kernel
  `6.12.94-123.180.amzn2023.x86_64`, Intel Xeon Platinum 8488C, 192 CPUs.
  Node 0 CPUs were `0-47,96-143`; node 1 CPUs were `48-95,144-191`; the
  distance matrix used 10 locally and 21 remotely. Dependent 512 MiB scratch
  source `c4a2c445...` measured a remote/local elapsed ratio of 1.5182
  [1.5066, 1.5299] for node-0-resident data and 1.5360 [1.5263, 1.5458] in the
  reciprocal node-1-resident direction. Each direction used eight complete
  four-process blocks, 32 fresh processes. Four-block, 16-process A/A controls
  were 0.9934 [0.9760, 1.0111] and 1.0025 [0.9938, 1.0113]. All 131,072 pages
  remained on the intended node before and after every measured treatment.

The brackets are the scratch probe's 95% paired intervals. Their narrowness is
run-window precision, not coverage of other hosts, builds, access patterns, or
long-lived automatic migration.

## Exact-source result

Commit `8edc18103c6649949ce393cfcf7a099327fcf92c` passed the full source,
workspace, placement, correctness, code-generation, and receipt gates on both
required hosts. The one-node Arm host provided a correctness-only control. On
the two-node `xxl` host, the reciprocal remote/local ratios were 1.5610
[1.5342, 1.5882] and 1.5540 [1.5362, 1.5721], each from eight complete blocks.
The corresponding A/A intervals included 1.0. These exact-source records
supersede the scratch values above; they do not broaden the host or workload
boundary.

See the [Arm control](measurements/arm-2026-08-04.md),
[`xxl` measurement](measurements/xxl-2026-08-04.md), and
[cross-host comparison](measurements/comparison-2026-08-04.md).

## Exact-source measurement contract

A retained performance record is admissible only when all of these gates pass:

- Name the repository commit and a short source prefix. Archive the exact topic
  source sent to each host; hash the archive and a sorted source manifest before
  the run and verify the source manifest again after the run.
- Record endpoint request, alias expansion, resolved hostname, architecture,
  CPU model, kernel, online and allowed CPUs/nodes, node CPU lists, distance
  matrix, SMT siblings, memory capacity, page size, automatic balancing, and
  transparent-huge-page state.
- Record compiler version, complete build command and environment boundary,
  final binary SHA-256, and inspected final-image access loop. A source symbol
  or source listing alone is insufficient.
- Run each timed treatment in a fresh process. Record initializer and worker
  CPUs and nodes, mapping bytes, page count, touch operation, access count,
  randomization seed, schedule, and timer boundaries.
- Query every page before and after the measured phase. Retain per-node counts,
  query failures, minor and major fault deltas, requested and observed CPUs,
  and a deterministic checksum. Never silently coerce a negative page status
  into a node identifier.
- Predeclare the complete block as the analysis unit, the A/B and A/A schedules,
  stopping count, exclusion rules, estimator, and interval. Retain every
  attempted process. Invalid attempts stay visible and are not replaced after
  inspecting their outcomes.
- Hash raw logs, summaries, manifests, code-generation evidence, and run status.
  A result is exact-source evidence only when the final status reports successful
  source verification and all placement and correctness gates.

Run and interpretation details live in [round 1](rounds/01.md). The retained
record format is in [measurements](measurements/README.md), and the operating
system contracts are in [references](references.md).

## Validate the model crate

From the repository root:

```bash
cargo test --package numa-first-touch-migration
cargo test --doc --package numa-first-touch-migration
```
