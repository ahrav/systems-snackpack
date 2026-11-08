# Topic 102 results

Tested source: `bc22e41763275f1a4fc11e751885b172d90e5f32`.
Archive SHA256: `3babd157386ce8b87f8992211c5658e92534f889ebb1369c821846c95c343b93`.

Python heap-based exact scan versus fixed-centroid IVF. These are teaching-model results.
Rust performance is unmeasured. The Rust companion passes two tests and one doctest on all three hosts.
Its independent absolute-distance ranking test checks 3100 results per host.

All three hosts pass 5760 Python/SQLite comparisons, seven invalid-input checks, and the boundary counterexample.
The oracle output digest agrees across hosts. All final measurements use the archived committed source.
The earlier Python-only campaign is retained separately and excluded from these results.

## Workload and controls

Four integer dimensions; k=5; 16 centroids from {0,100}^4; seed 102; 32 queries.
Tiny has 64 vectors and coordinate noise [-8,8]. Separated has 2048 vectors with that noise.
Overlap has 2048 vectors and noise [-70,70]. Noise is uniform integer and centroid choice is uniform.
Queries are independent draws from the same declared distribution. Centroids are fixed, with no training.
Each method has six fresh-process samples per workload: three rotated orders, each followed by its reverse.
Each worker warms the full query batch once. There are 72 measured workers and 72 warmup batches per host.
Timing includes query validation, routing, candidate materialization, scoring, heap selection, and result allocation.
Generation, startup, construction, and oracle checks are excluded. Construction times are recorded separately.
Exact scan can use the source array without constructing IVF lists. All methods use the same scoring and heap selection.
Linux affinity is CPU 0; local macOS affinity is uncontrolled. Host load, clocks, SMT, thermals, and host placement are uncontrolled.
Python versions differ between local and Linux. Cross-host ratios cannot isolate hardware effects.
Per-query times are batch averages. Ranges measure run variability; they do not estimate request-tail latency.

Quality floor: mean recall >=0.95 on these 32 queries. A winner must be at least 5% faster in every corresponding
round than every other qualifying method. Otherwise the result is unresolved. This rule was set before timing.
Independent held-out query strata, production libraries, float numerics, learned builds, graph/compressed indexes,
memory peaks, filtering, mutation, loaded latency, and GPU work remain outside the measurements.

## local

macOS-26.7.2-arm64-arm-64bit-Mach-O; Python 3.13.16.

CPU: arm.

| Workload | Method | Median us/query | Min-max us/query | Recall@5 | Mean candidates |
|---|---|---:|---:|---:|---:|
| tiny | exact | 23.46 | 22.77-27.95 | 1.00000 | 64.00 |
| tiny | ivf1 | 8.19 | 7.51-9.82 | 0.68750 | 3.94 |
| tiny | ivf4 | 13.97 | 12.92-14.86 | 0.99375 | 17.28 |
| tiny | ivf16 | 29.15 | 27.32-31.12 | 1.00000 | 64.00 |
| separated | exact | 621.05 | 615.90-629.01 | 1.00000 | 2048.00 |
| separated | ivf1 | 45.10 | 44.88-46.73 | 1.00000 | 127.50 |
| separated | ivf4 | 157.10 | 153.20-160.71 | 1.00000 | 508.53 |
| separated | ivf16 | 609.89 | 605.05-620.17 | 1.00000 | 2048.00 |
| overlap | exact | 634.52 | 627.87-671.26 | 1.00000 | 2048.00 |
| overlap | ivf1 | 50.40 | 48.83-54.59 | 0.71250 | 129.59 |
| overlap | ivf4 | 173.12 | 171.72-177.30 | 0.99375 | 518.41 |
| overlap | ivf16 | 646.68 | 638.70-648.36 | 1.00000 | 2048.00 |

Winners at the declared quality floor: tiny: ivf4, separated: ivf1, overlap: ivf4.

| Workload | IVF construction median ms | Min-max ms | List occupancy min-max |
|---|---:|---:|---:|
| tiny | 0.371 | 0.337-0.492 | 1-8 |
| separated | 10.864 | 10.682-12.018 | 108-149 |
| overlap | 10.889 | 10.772-13.339 | 103-141 |

## arm

Linux-6.12.113-138.209.amzn2023.aarch64-aarch64-with-glibc2.34; Python 3.9.25.

CPU: CPU implementer	: 0x41; CPU part	: 0xd40.

| Workload | Method | Median us/query | Min-max us/query | Recall@5 | Mean candidates |
|---|---|---:|---:|---:|---:|
| tiny | exact | 122.18 | 122.06-124.74 | 1.00000 | 64.00 |
| tiny | ivf1 | 43.42 | 43.28-43.67 | 0.68750 | 3.94 |
| tiny | ivf4 | 71.61 | 71.19-72.36 | 0.99375 | 17.28 |
| tiny | ivf16 | 153.21 | 152.71-157.42 | 1.00000 | 64.00 |
| separated | exact | 3613.87 | 3606.71-3641.99 | 1.00000 | 2048.00 |
| separated | ivf1 | 264.64 | 263.98-264.91 | 1.00000 | 127.50 |
| separated | ivf4 | 935.50 | 934.01-939.25 | 1.00000 | 508.53 |
| separated | ivf16 | 3651.57 | 3645.13-3654.84 | 1.00000 | 2048.00 |
| overlap | exact | 3638.24 | 3632.69-3646.84 | 1.00000 | 2048.00 |
| overlap | ivf1 | 274.80 | 274.19-276.16 | 0.71250 | 129.59 |
| overlap | ivf4 | 972.90 | 971.51-974.64 | 0.99375 | 518.41 |
| overlap | ivf16 | 3698.09 | 3692.99-3707.42 | 1.00000 | 2048.00 |

Winners at the declared quality floor: tiny: ivf4, separated: ivf1, overlap: ivf4.

| Workload | IVF construction median ms | Min-max ms | List occupancy min-max |
|---|---:|---:|---:|
| tiny | 1.993 | 1.978-2.077 | 1-8 |
| separated | 60.915 | 60.773-61.118 | 108-149 |
| overlap | 61.380 | 61.301-61.618 | 103-141 |

## x86

Linux-6.12.113-138.209.amzn2023.x86_64-x86_64-with-glibc2.34; Python 3.9.25.

CPU: model name	: Intel(R) Xeon(R) Platinum 8488C.

| Workload | Method | Median us/query | Min-max us/query | Recall@5 | Mean candidates |
|---|---|---:|---:|---:|---:|
| tiny | exact | 101.23 | 99.72-156.62 | 1.00000 | 64.00 |
| tiny | ivf1 | 36.05 | 35.63-40.87 | 0.68750 | 3.94 |
| tiny | ivf4 | 59.76 | 59.08-103.63 | 0.99375 | 17.28 |
| tiny | ivf16 | 143.90 | 124.36-169.69 | 1.00000 | 64.00 |
| separated | exact | 2892.53 | 2865.03-3624.51 | 1.00000 | 2048.00 |
| separated | ivf1 | 210.16 | 208.97-214.29 | 1.00000 | 127.50 |
| separated | ivf4 | 735.38 | 734.66-749.57 | 1.00000 | 508.53 |
| separated | ivf16 | 2914.66 | 2862.98-3224.26 | 1.00000 | 2048.00 |
| overlap | exact | 2969.52 | 2882.28-3895.31 | 1.00000 | 2048.00 |
| overlap | ivf1 | 225.91 | 220.50-234.36 | 0.71250 | 129.59 |
| overlap | ivf4 | 787.56 | 779.55-802.61 | 0.99375 | 518.41 |
| overlap | ivf16 | 2992.35 | 2968.69-3460.37 | 1.00000 | 2048.00 |

Winners at the declared quality floor: tiny: ivf4, separated: ivf1, overlap: ivf4.

| Workload | IVF construction median ms | Min-max ms | List occupancy min-max |
|---|---:|---:|---:|
| tiny | 1.608 | 1.597-2.946 | 1-8 |
| separated | 49.254 | 49.021-53.445 | 108-149 |
| overlap | 50.298 | 49.251-75.862 | 103-141 |

## Interpretation

One probe examines about one sixteenth of the large populations. Separated clusters achieve recall 1.0.
Tiny and overlap achieve 0.6875 and 0.7125 recall at one probe, below the chosen floor.
Four probes achieve 0.99375 on both. This supports workload-specific probe selection.
Full probing achieves recall 1.0 everywhere and retains routing/materialization costs.
Lower candidate work explains part of the timing difference; interpreter and allocation costs also contribute.
Build amortization requires the measured query volume and a real deployment workload.

## Reproduction

From this topic directory with Python 3.9 or later and Rust 1.93.1:

```bash
cargo test -p approximate-neighbors
cd experiment
python3 ann.py demo
python3 experiment.py check
python3 experiment.py bench > results.json
```

Raw final host data are in results/local.json, results/arm.json, and results/x86.json.
Each JSON includes exact source hashes, all timing samples, list sizes, affinity, and oracle results.

## Repository validation

All six required workspace commands passed with Rust 1.93.1: formatting, Clippy
with warnings denied, unit/bin/example tests (552 passed), doctests (160 passed),
benchmark compilation, and documentation with warnings denied. Writing policy
and the complete branch whitespace check passed. Command exit codes and timings
are in results/validation.json. Host unit/doctest logs and complete workspace logs
are retained with the standalone lesson output.

Preparation errors were corrected before final runs: one Cargo command and one
log inspection used the task directory instead of the repository directory.
Hook logging and credential-file write warnings occurred; hooks remained active
and Git operations completed. Final measurements used the archived source.
