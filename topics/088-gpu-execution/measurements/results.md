# Topic 088 evidence

2026-10-25. The retained CPU models establish address arithmetic and ownership.
CUDA compilation, sanitizer checks, device timings, and performance winners
remain unmeasured because the checked hosts expose no CUDA toolchain or NVIDIA
device. Host checks and final committed-source results are recorded below in the
results commit. The CUDA driver is a runnable candidate requiring device validation.

Derived full-warp results are deterministic: aligned contiguous four-byte values
touch four sectors, a one-word shift touches five, and a 1024-word stride touches
32. The pitch-32 shared column has 32 distinct words in one bank; pitch 33 has
one word in each bank. These counts do not predict a time ratio.
