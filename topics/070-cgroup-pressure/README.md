# Cgroup CPU budget and batch concurrency

Compare one, two and four workers on identical independent records under
uncapped, half-CPU/100 ms and half-CPU/10 ms policies. The experiment records
batch wall time, live quota readback, ancestor configuration, PSI and controller
deltas. It does not deliberately induce memory pressure or select a memory policy.

```bash
cargo test -p cgroup-pressure
python3 topics/070-cgroup-pressure/scripts/run.py /tmp/topic070-results
python3 topics/070-cgroup-pressure/scripts/analyze.py /tmp/topic070-results/runs.json
```

The runner requires Linux cgroup v2, a systemd user manager, Python 3.8+, Rust
1.93+, taskset, objdump and four eligible physical cores. It starts temporary
services with CPUWeight=100 and MemoryMax=128M. RuntimeMaxSec=20s initiates
stopping; it does not guarantee exit at exactly 20 seconds. The library tests
also run on macOS. The probe assumes the ordinary host cgroup mount at
/sys/fs/cgroup; it is not a namespace-general production collector.

See [experiment](EXPERIMENT.md), [results](measurements/README.md),
[round notes](rounds/01.md), and [sources](references.md).
