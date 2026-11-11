# Scoped skill audit

Source origin/main: `79154ae6ad673e3ea186c148a5493f9dcb56d4a8`.
No skill edit is justified for this lesson. Existing owners cover the VM
mechanism, version-sensitive page-size behavior, mapping-level measurement and
allocator attribution needed to apply the result. Synthetic metadata placement
and the glibc source example remain in the lesson and its sources.

Inspected current AGENTS.md, evals/RUNBOOK.md, PR template, writing/authoring
instructions, and these owners with references and canonical cases:

- mmap-and-virtual-memory-tuning: ordinary private fork views, first-write
  backing, THP split/base-page behavior, mapping measurement, overcommit,
  MADV_DONTFORK child semantics; cases 5, 6 and 10.
- allocator-selection-and-production-heap-sampling: live/usable/active/resident
  decomposition, metadata, spatial stranding, allocator-specific hypotheses and
  per-VMA attribution; cases 8, 9 and 12. Explicit large-page allocator advice
  is scoped separately from ordinary base-page COW.
- linux-service-memory-growth-and-oom-attribution: RSS double counting, PSS,
  cgroup charge boundaries and ownership before tuning; cases 1 through 5, 15.

The audit establishes sufficient existing guidance for this bounded topic. It
makes no new model-quality claim. Source main's unrelated .bilevel and ratatui
work and the existing algorithm worktree were preserved. No new skill campaign
or source PR applies. Evaluator work is the already eligible Topic104 merge sync.

Prior source PR420 and evaluator evidence PR52 are MERGED. The full prior run
was verified again on asm: topic104-rseq-20261110, seal
c936a42c9c3712b566883d405e4ff27b59e331ea3fe41a259484567c06fb22de.
It reports on47/72 off7/72 previous39/72, exploratory lifts +0.5556/+0.1111.
Four cases lose one pass each versus previous. Later case1 evaluation at
360f6763 reports 0/3 for all arms; this evidence is already published in PR52.
PR420's description is stale. Its actual merged head is df2558e0 and merge
commit cf96e027. No readiness or current-input quality claim follows from merge.
The published evaluator lock still pins304b6c58, so merge synchronization is due.
