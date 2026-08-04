# Measurements

Each retained host record must bind the result to one exact source candidate
and keep topology, policy, placement, mechanism, and timing as separate claims.

## Required record fields

- requested endpoint, runtime alias, resolved hostname, run window, kernel,
  architecture, CPU model, online and allowed CPU/node masks;
- CPU-to-node lists, distance matrix, SMT siblings, node memory, base page size,
  transparent-huge-page state, and automatic NUMA-balancing state;
- repository commit, source prefix, source-archive digest, sorted source
  manifests before and after the run, compiler and build command, final binary
  digest, and final-image access-loop evidence;
- mapping bytes and pages, initializer and worker CPUs/nodes, page-touch method,
  access count, schedule seed, fixed A/B or A/A schedule, and timer boundary;
- per-page query status before and after, per-node page counts, query failures,
  minor and major fault deltas, requested and observed CPU/node, checksum, and
  process exit status;
- every attempted process, complete-block inclusion decisions, block log
  contrasts, geometric ratio, interval method, dispersion, and A/A diagnostic.

## Claim rules

- A node distance matrix is topology, not measured latency.
- A per-page query is placement evidence, not a DRAM-traffic measurement.
- A final binary proves the access shape, not where pages or requests resided.
- Elapsed ratios are workload and run-window observations. They do not identify
  a socket interconnect, memory controller, or automatic-balancing action.
- A one-node host is a correctness control. It cannot produce a local/remote
  NUMA contrast.
- Failed, partial, and superseded candidates remain retained and labeled. They
  do not contribute to the fixed estimator.

Raw evidence belongs under `raw/<source-prefix>/<host-label>/`. The directory's
[`README`](raw/README.md) defines the bundle and hash contract. Measurement
notes must link to that evidence rather than copying only summary values.

The 2026-08-04 values in the [topic README](../README.md) are pre-artifact
scratch observations. They must not be copied into a retained record for the
checked-in candidate.
