# 2026-07-31 cross-host interpretation

Both hosts ran the same source commit, fixed native-build policy, correctness
gates, 512 MiB write workload, 500,000,000-iteration STLF workload, and
order-balanced process schedule. Each host produced 128 fresh-process records;
the four-process block is the analysis unit. Their binaries differ because
`target-cpu=native` targets different architectures and toolchain versions.

The x86-64 host showed a lower elapsed time for complete-line `VMOVNTDQ` plus
`SFENCE` writes than for temporal `VMOVAPS` writes: `B/A = 0.37581` with a 95%
between-block interval of `[0.37407, 0.37756]`. The Arm host's advisory `STNP`
comparison was unresolved: `B/A = 1.00235 [0.99220, 1.01260]`. This difference
is consistent with the architectural distinction between x86 streaming stores
and Arm's non-temporal allocation hint, but the experiment did not measure
cache allocation or memory traffic and therefore does not prove that mechanism.

Partial-overlap dependent loads were slower on both hosts. The observed ratios
were `1.91442 [1.91210, 1.91675]` on the Arm host and
`3.99082 [3.87434, 4.11079]` on `xxl`. These results establish geometry-specific
elapsed costs for the two final binaries. They do not establish a portable
latency constant or characterize other widths, alignments, offsets, or
independent throughput.

Do not compare absolute times between the hosts as an ISA contest. The machines
differ in CPU design, topology, kernel build, compiler version, virtualized
environment, and likely memory subsystem. The useful cross-host result is the
decision boundary: full-line non-temporal stores helped the measured x86
one-pass workload, `STNP` did not establish a benefit on the measured Arm host,
and exact store/load geometry mattered on both.
