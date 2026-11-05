# Topic 098 skill coverage

No source change is justified for this lesson's scope. Inspected source
origin/main: 125322bf6ca6c8d2eae5180afb38cd38af96e5d2.

The existing owner is systems-design:distributed-transactions-and-atomic-commit.
Its SKILL.md and four references cover durable prepare/decision ordering,
participant timeout hazards, coordinator recovery, presumed variants, retained
locks, vendor resolution operations, and consensus-integrated commit.
Canonical cases 1, 2, 3, 4, 7, and 8 cover timeout abort, missing durable records,
orphaned prepared transactions, partition assumptions, decision loss, and saga
selection. Cases 5, 6, and 9 cover operator resolution, read-only participants,
and the local-transaction route. These are coverage observations; historical
labels do not establish fresh model quality.

Inspected sibling descriptions: coordination-avoidance-design,
idempotency-and-unknown-outcomes, consensus-and-replicated-state-machine-design.
Their boundaries separate whether coordination is needed, request retries, and
replication from the atomic-commit owner. Read current source AGENTS.md,
evals/RUNBOOK.md, writing rules, PR template, and authoring standards; read local
and asm evaluator AGENTS.md and current command documentation. No matching open
atomic-commit source/evaluator PR was found. No model run or evaluator PR applies
because no skill input changed.

## Bounded prior-work check

Source PR377 and evaluator PR13 are MERGED. Published evaluator sources.lock.json
still pins 8005f00a99c257dd69d5abc318fac4984c7021de, which contains source merge
8427426b3b3daec7b0417a02d003b03732928350. Prior import synchronization is published.
The canonical topology case27 remains a routing-only question in quality evals.
Its scoped classification repair, calibration, committed-source paired/trigger
campaign, sealed report, and subsequent synchronization remain pending.
Baseline d024985f67e9dba9e2e4ba437049036a7bf41ba7; evaluated candidate, run ID,
and seal root remain unavailable. This does not block Topic098.

asm is reachable at evaluator b23a35dd328a24e9f8bbfb03bc8aabbcc5015894. Existing
untracked creusot evaluation directories were preserved. Source primary .bilevel
and the evaluator's unrelated local branch/worktree were preserved.
PR377 gate/validate are CANCELLED at its recorded head. Systems PR85 is MERGED
and all observed checks succeeded. Arm still has no Node executable on PATH;
both required Linux hosts still lack /dev/kvm. Those measurement follow-ups
remain pending with their original exact source instructions.

Two exploratory lookups used wrong paths (source.lock.json and the topology
skill under systems-design). Corrected to sources.lock.json and software-design;
no repository files were changed by those lookups.
