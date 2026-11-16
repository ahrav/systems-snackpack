# Topic 110 skill audit

No change justified at ahrav/ahrav-claude-plugins origin/main
`d2920181c6c01989bee873d361e682aee321948c`.

Inspected the source repository remotes, current worktrees and open PR inventory;
AGENTS.md, evals/RUNBOOK.md, PR template and docs/agents/writing.md; the
rust-code-reviewer owner, references/security.md and canonical case 4; and the
security-reviewer and rust-implementation sibling routes.

The existing owner explicitly covers canonicalize/check/open races, mutable
namespace components, operation-time directory capabilities, the limited scope
of plain openat and final-component O_NOFOLLOW, opened-handle metadata, hard
links, file types and permissions. Case 4 supplies the same adversarial rename
and symlink capability and requires a beneath policy during open. The owner
links primary openat2 and capability API contracts. This coverage addresses the
lesson's failure mechanism. No observed skill miss or conflicting guidance
justifies an edit. No model run, source PR or evaluator PR applies to this audit.
This is a source coverage finding, not a measured model-quality claim.

Trusted asm is reachable. Its existing evaluator checkout is at b23a35dd328a24e9f8bbfb03bc8aabbcc5015894.
Read its AGENTS.md and current dev/import command help. Retained unrelated runs
were preserved. The bounded prior-work check confirms evaluator PR59 MERGED
at bfeeded770591f711b623a4bba39ad1df5373b02. Its recorded checks job is CANCELLED;
security and Kilo review succeeded. This does not change the earlier executed
local validation or establish a new hosted pass. Previous fixture, calibration
and case-coverage follow-ups remain in curriculum pending_work. No new merged
skill change from this lesson requires evaluator synchronization.
