# Primary sources and version boundaries

The two retained targets run Linux 6.12 Amazon Linux kernels. The experiment
uses interfaces present there and records each live kernel, compiler, build
flags, executable, and source digest. Current kernel documentation can describe
later fixes, so behavior that affects deployment must be rechecked against the
deployed kernel source and configuration.

## Linux file-to-socket paths

- [`sendfile(2)` in the Linux man-pages project](https://man7.org/linux/man-pages/man2/sendfile.2.html)
  defines its file-description restrictions, short-progress behavior,
  `0x7ffff000` per-call limit, offset semantics, and the requirement not to
  modify shared source pages before the receiver consumes them. It also states
  that a pipe output uses `splice` behavior since Linux 5.12. The man-pages
  site follows current Linux man-pages rather than the measured 6.12 kernels.
- [`splice(2)` in the Linux man-pages project](https://man7.org/linux/man-pages/man2/splice.2.html)
  requires at least one pipe endpoint and defines partial results, error cases,
  and flags. It records that `SPLICE_F_MOVE` has been a no-op since Linux
  2.6.21 and that `SPLICE_F_NONBLOCK` does not make the non-pipe endpoint
  nonblocking.
- [Linux 6.12 splice documentation](https://docs.kernel.org/6.12/filesystems/splice.html)
  describes splice pipes as buffers that can hold references to pages rather
  than copying payload bytes into every pipe buffer.
- [Linux 6.12 page-cache documentation](https://docs.kernel.org/6.12/mm/page_cache.html)
  defines the page cache used by the experiment's prewarmed memory-backed file
  path. It does not prove that a particular timed read remained resident.

## Application-backed zero-copy

- [Linux `MSG_ZEROCOPY` documentation](https://docs.kernel.org/networking/msg_zerocopy.html)
  defines `SO_ZEROCOPY`, the per-call flag, successful-send identifiers,
  inclusive and possibly coalesced completion ranges, 32-bit wrap, copied
  fallback, error-queue processing, the local-reuse meaning of completion, and
  resource-limit failures. It also states that loopback always reports copied
  fallback and presents roughly 10 KiB as an implementation-note threshold,
  not a universal application crossover.
- [Linux 6.12 `msg_zerocopy` selftest](https://github.com/torvalds/linux/blob/v6.12/tools/testing/selftests/net/msg_zerocopy.c)
  is the kernel project's executable example for socket setup, error-queue
  parsing, completion ranges, copied fallback, and buffer lifetime. The topic's
  smaller control is independent code and does not claim full selftest coverage.
- [`socket(7)` in the Linux man-pages project](https://man7.org/linux/man-pages/man7/socket.7.html)
  defines the socket error queue and `sock_extended_err` metadata used to
  validate asynchronous notifications.

## Encryption boundary

- [Linux kernel Transport Layer Security documentation](https://docs.kernel.org/networking/tls.html)
  defines kernel TLS transmit behavior. Its software path creates an encrypted
  scatterlist and encrypts into a new buffer; direct transmission is not an
  automatic consequence of `sendfile`.
- [Linux kernel TLS device-offload documentation](https://docs.kernel.org/networking/tls-offload.html)
  defines the separate device-offload path, resynchronization obligations, and
  the `TLS_TX_ZEROCOPY_RO` read-only source contract for a zero-copy transmit
  optimization.

## Measurement and analytical models

- [`clock_gettime(2)` in the Linux man-pages project](https://man7.org/linux/man-pages/man2/clock_gettime.2.html)
  defines `CLOCK_MONOTONIC_RAW`, used for the probe's in-process intervals.
- [`getrusage(2)` in the Linux man-pages project](https://man7.org/linux/man-pages/man2/getrusage.2.html)
  defines the sender and child CPU-time observations.
- [`sched_getaffinity(2)` in the Linux man-pages project](https://man7.org/linux/man-pages/man2/sched_getaffinity.2.html)
  defines the allowed-CPU evidence and the affinity boundary used by the
  focused experiment.
- [National Institute of Standards and Technology guidance on randomized block
  designs](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
  motivates balancing order within a complete block. The experiment uses a
  fixed seeded schedule and does not claim random sampling of machines.
- [National Institute of Standards and Technology confidence interval for a
  mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm)
  defines the Student-t working-model interval applied to complete-block log
  contrasts. Sequential blocks do not establish the model assumptions.
- [John D. C. Little, “A Proof for the Queuing Formula: L = lambda W,” 1961](https://doi.org/10.1287/opre.9.3.383)
  proves the long-run average relationship used for the outstanding-buffer
  capacity screen. The model estimates a mean and supplies no tail guarantee.

## Model boundary

The named-copy, serial-time, bounded-pipe, page-span, and held-memory equations
are checked analytical models in this crate. The kernel sources do not expose
them as end-to-end runtime predictors. The models omit overlap, queueing,
cache effects, page-reference work, protocol processing, encryption, device
movement, completion tails, and contention unless the caller supplies an
explicit additional term.
