# Scoped skill audit

No source skill change is justified for today's translation and memory-policy
scope at source origin/main 38699844e6716cde4327df455e15601d82e64063.
The checked local skill and instruction files have no diff from this revision.

Inspected AGENTS.md, evals/RUNBOOK.md, PR template, writing instructions, the
TLB/address-translation owner, its reach, huge-page and measurement references,
and relevant canonical cases including 12, 16, 17, 18 and 20. Case 12 covers the
24-read cold bound; case 20 separates architecture and shadow paging; case 16
limits smaps conclusions. The mmap owner and page-fault reference cover backing,
residency and fault-accounting boundaries. Scheduler diagnosis sibling guidance
covers guest steal-time attribution. This audit establishes coverage for the
scoped decisions; it does not claim a general hypervisor implementation skill.

No changed skill inputs, new suite, model run, plugin PR, or evaluator PR apply.
No quality or lift result is claimed.

Read evaluator AGENTS.md and current command documentation. The trusted asm
operator is reachable at evaluator 1022f20c688aaced14dbda92f0a1f514a29f2ef7.
Its concurrent changes and retained runs were preserved. Development help
supports --source-ref, --baseline, --arms, --trials and trigger options.

Bounded earlier-work check: source PR377 and evaluator PR13 remain MERGED.
Current evaluator main sources.lock.json pins source 8005f00a, which already
contains the earlier source merges. No newly eligible synchronization was found.
Canonical software-design/in-process-concurrency-topology-design case 27 is
still a routing-only prompt in the quality evals. Topic087 retains its pending
classification repair, calibration, on/off/previous three-trial and trigger
campaign using pre-change baseline d024985f, and sealed-report verification.
Evaluated candidate, run ID and seal root remain unavailable. Today's audit
leaves those pending actions intact.

Topic095 Arm Node replay remains pending: Node is still absent from PATH on the
required Arm host. Earlier runtime-location checks are retained with that lesson.
