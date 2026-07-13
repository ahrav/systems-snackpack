# References

## Linux ABI and tools

- [`perf_event_open(2)`](https://man7.org/linux/man-pages/man2/perf_event_open.2.html): event grouping, time scaling, `precise_ip`, and record flags.
- [`perf-list(1)`](https://man7.org/linux/man-pages/man1/perf-list.1.html): event modifiers, strong and weak groups, and architecture mappings.
- [`perf-stat(1)`](https://man7.org/linux/man-pages/man1/perf-stat.1.html): counter output, metric grouping, and interval mode.
- [`perf-record(1)`](https://man7.org/linux/man-pages/man1/perf-record.1.html): period and frequency sampling, call graphs, and buffer sizing.
- [Kernel perf ring buffer](https://docs.kernel.org/userspace-api/perf_ring_buffer.html): producer-consumer behavior and loss records.
- [Kernel perf security](https://docs.kernel.org/admin-guide/perf-security.html): `perf_event_paranoid` and `CAP_PERFMON`.
- [Kernel perf sampling controls](https://docs.kernel.org/admin-guide/sysctl/kernel.html#perf-cpu-time-max-percent): sample-rate throttling.

## Architecture mechanisms

- [Intel Performance Monitoring Events glossary](https://perfmon-events.intel.com/glossary/): precise-eventing IP and precise distribution fields.
- [Intel TPEBS and PEBS overview](https://www.intel.com/content/www/us/en/developer/articles/technical/timed-process-event-based-sampling-tpebs.html): PEBS capture and precise distribution limits.
- [AMD IBS overview](https://docs.amd.com/r/en-US/68658-uProf-getting-started-guide/Introduction-to-IBS-Instruction-Based-Sampling): fetch and operation sampling.
- [`perf-arm-spe(1)`](https://man7.org/linux/man-pages/man1/perf-arm-spe.1.html): Arm SPE selection, jitter, collisions, and synthetic samples.

## Empirical studies

- [Fuse: Accurate Multiplexing of Hardware Performance Counters Across Program Phases](https://research.manchester.ac.uk/files/59933625/TACO_submission_v2.pdf): phase-dependent multiplexing error.
- [Tintin: Efficient Multiplexing of Hardware Performance Counters](https://www.usenix.org/system/files/osdi25-li.pdf): counter-capacity and multiplexing measurements.
