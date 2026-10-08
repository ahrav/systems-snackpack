# Primary sources

- [Linux 6.12 cgroup v2 ABI](https://www.kernel.org/doc/html/v6.12/admin-guide/cgroup-v2.html): hierarchy, CPU and memory interfaces.
- [Linux 6.12 bandwidth control](https://www.kernel.org/doc/html/v6.12/scheduler/sched-bwc.html): quota, period, runtime slices and burst caveats.
- [PSI ABI](https://github.com/torvalds/linux/blob/v6.12/Documentation/accounting/psi.rst): wall-time stall signals and scope.
- [Fair scheduler](https://github.com/torvalds/linux/blob/v6.12/kernel/sched/fair.c): enforcement accounting.
- [Memory controller](https://github.com/torvalds/linux/blob/v6.12/mm/memcontrol.c): high, max and OOM paths.
- [systemd v256 resource control](https://github.com/systemd/systemd/blob/v256/man/systemd.resource-control.xml): CPUWeight controller enablement, quota and memory properties.

Host kernels are vendor 6.12 builds, not an assertion of byte-identical upstream
source. Generated assembly and deployed versions are retained with raw evidence.
