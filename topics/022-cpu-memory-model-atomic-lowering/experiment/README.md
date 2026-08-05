# Experiment

`run_host.sh` records correctness, native and generic lowering, a bounded
store-buffering observation, and order-balanced cost processes on one Linux
host.

```bash
HOST_ARGUMENT=xxl ./topics/022-cpu-memory-model-atomic-lowering/experiment/run_host.sh /tmp/topic22-xxl
```

The default CPU roles are cost CPU 3, workers 0 and 1, and coordinator 2.
Override them with `COST_CPU`, `WORKER_CPU0`, `WORKER_CPU1`, and
`COORDINATOR_CPU`. Verify that all selected CPUs are allowed, distinct where
required, and appropriate for the topology under test.

The cost driver uses 12 ABBA/BAAB blocks. Processes, not inner-loop operations,
are the samples. The store-buffering counts are bounded observations. A zero
count does not prove that the language or architecture forbids an outcome.
