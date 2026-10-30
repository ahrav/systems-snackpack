# Topic 093 skill audit

No skill change is justified for this lesson's scoped obligations at source origin/main
`c11eda581ef82c6992fcf65162e501b65fd28b63`.

Read the source AGENTS.md, writing instructions, PR template, external-runner procedure,
existing owners, references and relevant canonical cases. The source primary checkout has
preexisting untracked .bilevel content; it was preserved. No matching open wire PR was found.

- implementation:rust-implementation, serde-and-data-modeling.md: slice-backed borrowed
  deserialization, lifetime bounds, owned reader APIs, strictness and validated domain boundaries.
  Canonical case 7 distinguishes owned task configuration from legitimate borrowed views.
- low-level-systems:zero-copy-buffer-lifecycle, lifecycle-method.md: named copy boundary,
  lifetime-bound views, immutable access authority, static range/arithmetic checks, temporal
  validity, held-memory bounds and offset-relative layouts. Cases 1 and 4 cover static validation
  versus live access rights and concurrent external writes to borrowed bytes.
- systems-design:schema-and-wire-compatibility, format-rules.md and compatibility-gates.md:
  field identity, defaults, unknown fields, value domains and deploy order. Cases 2, 3 and 6
  cover tag reuse, widened values and fixed-layout sentinel compatibility.
- software-design:representation-and-model-boundary-design: translation contracts and routing
  to encoding implementations and schema compatibility. Sibling boundaries remain distinct.

This is source-coverage evidence. Runtime routing accuracy, behavioral lift and complete library-specific
FlatBuffers/Cap'n Proto guidance were not evaluated. The lesson's new executable experiment belongs in
systems-snackpack; it does not establish a defect in these skill contracts. No model run or evaluator
PR is required because no skill or evaluator input changed.

## Bounded prior-work check

Source PR377 and evaluator PR13 remain MERGED at da7e55113a9cbc749640b8eb4865b2357d8cd7eb
and 143248f2a9986385019186e1d2e582bd4187a48c. Source case27 still routes an OS scheduler
question inside the topology quality suite. Its classification correction and full model campaign
remain pending with explicit baseline d024985f67e9dba9e2e4ba437049036a7bf41ba7.
Evaluated commit, run ID and seal root remain unavailable for that campaign.

asm is reachable at evaluator 71189eafe26dfe2e9e8fbe4da2e234a070754787. Read its AGENTS.md and
current ske dev command help. Existing untracked runs were preserved. Import synchronization was
already published through PR13. No new merged skill change in today's scope requires an import.
PR377 gate and validate checks are CANCELLED at its current merged head; security checks passed.
Systems PR85 is MERGED at cbb34c8dcb6267690c3e0a1de752b36ed1b4f365 with all listed checks successful.
These current-head observations do not retroactively establish results at older heads.
