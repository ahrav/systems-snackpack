# Topic087 Linux measurements

Static chunks win at grain 1 and have lower medians at grain 64 on both hosts. At grain 1024, static and stealing are an operational tie for these samples: every median differs by less than 0.4%. This is a practical selection from six observations per mode, rather than a statistical equivalence test.

Measured source commit: `4a8ffe7be8d0b60d36d5a3913897cf1bd0f13570`. File hashes and archive identity are in [source.json](source.json). Both hosts ran the exact archived source. Later documentation commits retain these measured bytes.

## Workload and controls

Each invocation processes 262144 items with 32 base mixing rounds and four workers. Skew 1 gives equal work per item. Skew 16 makes every nineteenth item cost sixteen times as much, distributing expensive items across every static chunk. This does not test a clustered imbalance where stealing may help. Grains are 1, 64 and 1024 items.

Each cell has one warmup process per mode and six measured permutations of serial, static and stealing. Every measured mode runs once in a fresh process. Across six cells, each host executes 18 warmups and 108 measured processes. Cell order uses seed 87. Timing includes allocation, thread creation, computation, joins and cleanup, and excludes process startup and compilation. Serial performs the same computation without pthread creation. Successful steals are recorded in raw.csv.

Each runner and its children use CPUs 0, 1, 2 and 3, verified as distinct cores on NUMA node 0. Threads may migrate within that set. Neither host is reserved against unrelated processes, frequency changes or SMT-sibling load. The two curriculum jobs coordinated their timed campaigns; cross-host differences cannot be attributed solely to architecture.

Both use GCC 11.5.0 with `-std=c11 -O3 -Wall -Wextra -Werror -pthread`. The mutex queues, shared sum and completion atomics, deterministic victim order, and linear-time thief removal are part of the measured implementation. This measures bounded CPU batches with new workers per call.

## Observations

Times below are median [minimum, maximum] milliseconds across six processes.

| Host | Skew | Grain | Serial | Static | Stealing |
|---|---:|---:|---:|---:|---:|
| arm | 1 | 1 | 13.760 [13.652, 13.825] | 3.555 [3.536, 3.568] | 61.783 [56.772, 64.232] |
| arm | 1 | 64 | 13.779 [13.698, 13.817] | 3.577 [3.525, 3.594] | 3.982 [3.906, 4.027] |
| arm | 1 | 1024 | 13.742 [13.724, 13.815] | 3.571 [3.538, 3.619] | 3.560 [3.537, 3.582] |
| arm | 16 | 1 | 29.056 [28.964, 29.095] | 7.412 [7.409, 7.421] | 52.109 [49.982, 59.518] |
| arm | 16 | 64 | 29.112 [29.048, 29.138] | 7.445 [7.419, 7.537] | 7.712 [7.591, 7.790] |
| arm | 16 | 1024 | 29.072 [28.957, 29.138] | 7.425 [7.417, 7.468] | 7.405 [7.359, 7.451] |
| xxl | 1 | 1 | 15.041 [15.002, 15.074] | 3.909 [3.892, 7.685] | 78.309 [61.988, 86.956] |
| xxl | 1 | 64 | 15.014 [14.994, 15.393] | 3.895 [3.876, 3.919] | 4.167 [4.131, 4.256] |
| xxl | 1 | 1024 | 15.014 [14.994, 15.137] | 3.902 [3.885, 3.971] | 3.903 [3.887, 3.935] |
| xxl | 16 | 1 | 35.805 [35.770, 35.884] | 9.087 [9.067, 9.101] | 75.724 [50.809, 90.134] |
| xxl | 16 | 64 | 35.809 [35.769, 35.919] | 9.111 [9.074, 18.045] | 9.422 [9.302, 12.597] |
| xxl | 16 | 1024 | 35.801 [35.761, 35.836] | 9.099 [9.075, 9.156] | 9.128 [9.092, 9.149] |

Arm: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, AArch64, 64 logical CPUs. xxl: `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, x86-64, Intel Xeon Platinum 8488C, 192 logical CPUs. Full kernel, topology, compiler and run timestamps are in each metadata.json.

Grain-1 stealing has 7.0 to 20.0 times the static median. Grain 64 costs 3.4% to 11.3% more by median; static wins 23 of the 24 within-block comparisons. The xxl grain-64 skew-16 static maximum is 18.045 ms, roughly twice its median. Retain this observation as variability; these data do not identify its cause.

Inference: choose static chunks for these evenly distributed batches. Grain 1024 removes most scheduling overhead for this stealing implementation, but these measurements provide no reason to replace static scheduling here. Test clustered or data-dependent imbalance before selecting stealing for another workload.

## Correctness and regression

Both hosts passed 325 Python accounting cases, 72 native serial/static/steal cases, 45 independently implemented Python checksum cases covering all three modes, and four per-item exactly-once checks. The checksum arithmetic wraps at 64 bits. Every measured row matched its cell checksum.

The forced regression pauses a splitter after publishing its first child. The child finishes before the second child is published. The repaired scheduler retains one outstanding obligation; a mutation that publishes before incrementing exposes zero. The mutant can still produce the expected checksum, so worker retirement is checked separately. These tests cover the exercised schedules; they are not a weak-memory proof.

## Reproduce

From a Linux checkout containing the topic, run:

```sh
cd topics/087-work-stealing
python3 scripts/validate.py
python3 scripts/run_campaign.py --source-commit 4a8ffe7be8d0b60d36d5a3913897cf1bd0f13570 --output measurements/replay
```

The replay command requires four allowed distinct cores on one NUMA node. Record the actual commit when replaying another source revision. The retained raw.csv, attempts.jsonl, validation.json, metadata.json and transfer.json files preserve observations and source identities for each host.

Earlier macOS timings used the completion-accounting bug and are superseded by this campaign. Their original files remain in the prior lesson output directory.
