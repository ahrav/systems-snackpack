# Restartable per-CPU counters

`experiment/counter.c` compares shared relaxed atomics, volatile thread-local
updates, and a Linux rseq update. All methods expose an exact total after join.
The Rust crate models interrupted updates against a serial event-list oracle.

```sh
cargo test -p restartable-sequences
cd topics/104-rseq/experiment
cc -O2 -std=c11 -Wall -Wextra -Werror -pthread counter.c counter.S -o counter
GLIBC_TUNABLES=glibc.pthread.rseq=0 ./counter rseq 8 1000000 2 0
python3 campaign.py ./counter > results.json
```

The native example requires Linux x86-64 or little-endian AArch64, rseq syscall
access, and eight permitted CPU IDs for the full campaign. Registration belongs
to this standalone executable; the glibc tunable disables libc registration.
Registration and affinity failures exit with an error. Production integration
requires coordinated registration ownership or a supported fallback.

The critical section checks CPU identity, computes in registers, and ends with
one aligned store. Abort redirects control flow and retries with a fresh CPU ID.
Preemption on the same CPU and migration both matter. Successful completion
commits once. Writes before the committing instruction would survive an abort.
The signal handler performs no nested operation. Assembly accesses the slots;
C reads them only after worker joins. Registered areas outlive all operations.
The demonstration supports CPU IDs below CPU_SETSIZE and rejects larger IDs.

Each slot has 128-byte alignment. Each TLS update is volatile to retain every
load/store, representing observable per-request accounting. Volatile is used
only for thread-private storage and kernel-updated ABI reads. Concurrent live
aggregation requires a separate safe access and snapshot protocol.

The stress controller repeatedly changes worker affinity and sends SIGUSR1.
Workers remain alive behind a final barrier until the controller stops. A delay
inside the protected interval increases interruption exposure only in stress
runs. Performance runs use zero delay and exclude controller activity.

## Sources

- [Linux v6.12 rseq protocol](https://github.com/torvalds/linux/blob/v6.12/kernel/rseq.c)
- [Linux userspace ABI](https://github.com/torvalds/linux/blob/v6.12/include/uapi/linux/rseq.h)
- [x86 signatures and descriptors](https://github.com/torvalds/linux/blob/v6.12/tools/testing/selftests/rseq/rseq-x86.h)
- [Arm signatures and descriptors](https://github.com/torvalds/linux/blob/v6.12/tools/testing/selftests/rseq/rseq-arm64.h)
- [TCMalloc per-CPU cache design](https://google.github.io/tcmalloc/design.html#restartable-sequences-and-per-cpu-tcmalloc)

See RESULTS.md for exact-source evidence and measurement limits.
