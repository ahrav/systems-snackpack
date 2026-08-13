# Two-host comparison for `b8d7f88`

Both required hosts built and ran the same source archive. All generic and
native correctness checks, workspace gates, 112-process timing schedules,
independent receipt validations, source-manifest comparisons, and linked-code
checks passed.

## What agreed

The direction of every candidate-to-left-to-right result agreed across hosts
and modes:

- Horspool led on the uniform-looking absent case and the skewed-text late
  match. Its ratios ranged from 0.318 to 0.709.
- Horspool lost on the prefix trap and the tiny late match. It collapsed on the
  suffix trap, with ratios from 49.004 to 50.269.
- Knuth-Morris-Pratt (KMP) led only on the repeated-prefix trap, with ratios
  from 0.761 to 0.951. It lost on the other four cases.
- `reuse` and `one_shot` ratios were close within each exact case and host.
  This workload does not establish that preparation is generally negligible;
  long scans dominate most cells, and the tiny case uses only four needle
  bytes.

The result supports selection by workload rather than by algorithm name. It
does not rank a production hybrid such as `memchr`, and it does not estimate
the prevalence of any synthetic case in production data.

## What differed

The exact x86 binary showed larger KMP penalties outside the prefix trap and a
larger KMP advantage within that trap. Horspool's favorable ratios were also
closer to one on x86, while its suffix-trap collapse was similar on both hosts.
These are measured cross-binary differences. CPU pipeline, cache, allocator,
and branch explanations remain inferred because the experiment collected no
hardware performance counters.

Linked-code inspection found scalar search loops on both hosts. The compiler
vectorized Horspool's 256-entry table initialization with SVE on Arm and AVX2
on x86. The binaries and plan-construction code differ, so no timing result may
be generalized to Arm, x86, Intel, or another compiler target.

## Evidence identity

| Field | Arm | `xxl` |
| --- | --- | --- |
| Source commit | `b8d7f88a25aede60fb589099239c771285450293` | same |
| Source archive SHA-256 | `5a280744...640c` | same |
| Processes / timing rows | 112 / 1,120 | 112 / 1,120 |
| Candidate blocks / A/A blocks | 12 / 4 | 12 / 4 |
| Receipt validator | PASS | PASS |
| Internal archive manifest | 379 entries, PASS | 379 entries, PASS |

See the [Arm record](b8d7f88-arm.md), [`xxl` record](b8d7f88-xxl.md), and
[raw archive hashes](raw/b8d7f88/SHA256SUMS).
