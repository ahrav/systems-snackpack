# Topic 102 skill coverage

No source skill change is justified by this lesson's scope.
Inspected source origin/main: 66e8d66a8dcb3a5e79efedc997b66d64929f6675.

The existing owner is search-systems/vector-index-selection-and-tuning. Its
SKILL.md and access-method, measurement, filtered-search, and exact-baseline
references cover fixed metric/ID contracts, eligible-subset oracles, IVF list
skew and scan caps, full-list coverage, HNSW construction/query breadth, recall
versus fill, memory, updates, and reproducibility. Relevant canonical cases
3/4/6/10/17/19/20/22/24 cover exact crossover, nprobe, build variability, compressed
search acceptance, empty denominators, reranking limits, exhaustive controls,
metric mismatches, and snapshots. Sibling owners cover exact execution,
quantization, and retrieval relevance/lifecycle. Their boundaries match today's
lesson. Inspection establishes coverage; it makes no new model-quality claim.

Read current source AGENTS.md, evals/RUNBOOK.md, writing rules, and PR template.
Read evaluator AGENTS.md and trusted asm dev command help. Source/evaluator
remotes and worktrees were inspected. Existing untracked source and evaluator
work was preserved. No candidate skill, new case, or evaluator change was created,
so a new development evaluation or companion evidence PR is inapplicable.

One bounded prior-work status check: source PR412 remains MERGED. Evaluator PR39
remains OPEN at 864019a9f6deadae17f63e422bc702388c22381c; offline checks QUEUED,
GitGuardian SUCCESS, CodeRabbit SKIPPED. asm is reachable at evaluator checkout
b23a35dd328a24e9f8bbfb03bc8aabbcc5015894 with concurrent runs present.

Prior pending work remains: validate calibration for revised incremental cases;
run fresh incremental on/off plus triggers and perf-pipeline on/off/previous
three-trial evaluation with explicit 80fd4be9d1b12ea0455206c2253a9620aee03f21
baseline; verify exact candidate identity and seals; investigate declining cases;
retain evidence in an evaluator draft. Current merged-input run ID/seal remain
unavailable. PR39 already publishes the prior exact-source import and evidence.
No duplicate synchronization or evidence PR was created.
