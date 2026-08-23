# CPU model details

Captured after the measurement run from the same authorized targets.
The raw sidecars are [`arm-cpuinfo.txt`](arm-cpuinfo.txt) and
[`xxl-cpuinfo.txt`](xxl-cpuinfo.txt).

This sidecar is not part of either immutable result archive. The `xxl` archive
also records its details in `host.txt`; the Arm archive reports vendor `ARM`,
model `1`, and stepping `r1p1`, but not the implementer and part identifiers
below.

## Arm

- CPU implementer: `0x41`
- CPU architecture: `8`
- CPU variant: `0x1`
- CPU part: `0xd40`
- CPU revision: `1`
- Features include `asimd`, `sve`, `dit`, and `bf16`.

## `xxl`

- Vendor: `GenuineIntel`
- Model name: Intel Xeon Platinum 8488C
- Family: `6`
- Model: `143`
- Stepping: `8`
- Microcode: `0x2b000670`
- The host reported KVM full virtualization and two hardware threads per core.
