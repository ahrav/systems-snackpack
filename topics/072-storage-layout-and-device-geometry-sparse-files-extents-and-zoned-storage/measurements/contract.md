# Measurement contract

Frozen before the initial Linux campaign. Three candidates, eight workloads:
64 KiB empty/scattered/dense; 16 MiB empty/scattered/clustered/dense;
65,553 bytes scattered. A 4 KiB write occurs at every 64th block for
scattered input; clustered uses the same number of blocks at the start.

Each cell uses one warmup per candidate and six independent process blocks,
one for each permutation of candidate order: 24 warmups and 144 measured
processes per host. Separate retained-map probes add three correctness runs.
The winning candidate must beat every rival by at least 5% in all six paired
blocks using ready_ns + rewrite_ns. Otherwise report unresolved. Report
median and observed minimum/maximum, not a confidence interval or p99.
Do not pool prelesson and exact committed-source campaigns.

Use disk-backed task-owned directories, default release target features,
no RUSTFLAGS, and one allowed CPU via taskset. Record hostname, architecture,
kernel, CPU model, toolchain, feature cfg, filesystem/mount options, device
geometry, and source/runner/binary identities. Never drop global caches.
The before-overwrite byte oracle makes that pass cache-warm.

Allocation is sampled after the first file sync while the writer is open.
Filefrag probes are separate processes inspected after verification and close.
Their counts can differ. Background filesystem and cloud activity is uncontrolled.
Only byte content and modeled zone placement are correctness contracts;
allocation counts and elapsed times are observations of this host/workload.

To replay outside the workspace, copy Cargo.toml, src/lib.rs,
examples/layout.rs, scripts/run.py and the retained source-identity.json
into a fresh directory. Run `python3 scripts/run.py`. The script requires
Linux, cargo, taskset, filefrag, findmnt, lsblk and free disk space. It creates
new data/evidence directories and refuses to reuse existing ones. Keep the
identity JSON's source paths unchanged and verify hashes before execution.
