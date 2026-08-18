# Raw evidence

The dated source-identity directory binds both retrieved host archives to one
Git-created source archive and records Secure Hash Algorithm 256-bit (SHA-256)
digests, which are content fingerprints. Each host archive also contains its
own file-and-digest list
(manifest). The evidence-only commit must not change the source that produced
the receipts, meaning the retained, machine-verifiable records from the host
runs.

The most recent run is under
[`2026-08-18-2bb0d3e`](2026-08-18-2bb0d3e/). It is historical: later review
commits changed the probe's receipt contract and the process receipt schema, so
no retained run validates the current branch source, and both hosts must be
rerun from the published source. The hardened
[`2026-08-18-f43f0fe`](2026-08-18-f43f0fe/), final-gate
[`2026-08-18-ef1b55f`](2026-08-18-ef1b55f/), post-review
[`2026-08-18-068d082`](2026-08-18-068d082/), intermediate
[`2026-08-18-a56a48e`](2026-08-18-a56a48e/), and initial
[`2026-08-18-3aaece9`](2026-08-18-3aaece9/) runs remain as historical
evidence for the commits they name.
