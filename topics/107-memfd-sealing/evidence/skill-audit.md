# Scoped skill audit

Baseline source: 2f589197238a15c28ba7204a553e7c8a24bb65ba.
Read source AGENTS.md, eval runbook, PR template, writing rules and miss policy;
read evaluator instructions and commands at 42312f42731a43226b93c5c766727fa890e3ef69.

Inspected zero-copy-buffer-lifecycle entrypoint, shared-memory reference,
canonical cases, and DMA cross-process-mapping sibling guidance. Existing
coverage establishes object identity, shrink prevention and lifetime. The
immutable-versus-ongoing-writer seal policy and receiver validation order were
missing. Extend the existing shared-memory reference and add cases 12 and 13.
This is a coverage extension with no observed agent-miss claim.

Candidate ba55131a67c205a247339a6306c1586e4229a1e3 is published in draft
https://github.com/ahrav/ahrav-claude-plugins/pull/422.
Both manifests are 0.20.64. Tier0, committed gate, writing and inventory pass.
Full Linux source tests execute 563 with 10 failures and 13 skips. The ten
failures concern unchanged rust-code-reviewer and skill-forge files and reproduce
in focused tests from unchanged main. macOS also has 14 Linux-only test errors.

The 13-case on/off/previous three-trial run topic107-memfd-20261113 is active on
asm in /local/home/ahrav/scratch/topic107-operator/ahrav-skill-evals.
Actual on/case input commit and previous baseline match the revisions above.
Description and trigger inputs are unchanged; routing probes are unrun.
Calibration metaeval-20261113T143838Z-112033 verifies seal
469247860ba8b4a7d312747f8f8a7ac0328cf624d85941d6274fe4513c845ae1.
The generator labeled two outputs good; one passed the judge and five mutants
failed. Manual review rejects the c0012 reference: it trusts pre-seal fstat,
permits an unverifiable FUTURE_WRITE alternative, and substitutes flush for
writer completion. c0013 overstates restrictions on private mappings. These are
invalid calibration references, not skill-quality results. Fresh calibration,
full-run verification, retained evidence publication and postmerge sync remain.

Prior PR421 and evidence PR54 are merged. Evaluator main already pins their
merged source 2f589197. Its topic106-postmerge-sync.md records current-input
run topic106-userfaultfd-merged-20261113, 27/48 on, 2/48 off, 25/48 previous;
cross-family calibration remains pending. This daily run also verifies the
older topic106-userfaultfd-20261112 seal b492a9e77bbd39247b417e640505a6439d9e21e4b8918143533d6f5967d57368.
