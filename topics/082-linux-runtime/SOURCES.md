# Primary sources

Read 2026-10-19. API documentation and source snapshots serve different purposes.
The experiment records each deployed kernel; source versions below explain the
mechanism without claiming a byte-identical vendor implementation.

- [vDSO](https://man7.org/linux/man-pages/man7/vdso.7.html): libc use, kernel mapping and architecture boundaries.
- [clock_gettime](https://man7.org/linux/man-pages/man2/clock_gettime.2.html): clock semantics and monotonicity.
- [epoll](https://man7.org/linux/man-pages/man7/epoll.7.html): readiness, ET, fairness, lifetime and coalescing.
- [epoll_wait](https://man7.org/linux/man-pages/man2/epoll_wait.2.html): timeouts, rounding and signals.
- [hrtimers](https://docs.kernel.org/timers/hrtimers.html): high-resolution timers versus the timer wheel.
- [timerfd](https://man7.org/linux/man-pages/man2/timerfd_create.2.html): absolute deadlines and expiration counts.
- [timer slack](https://man7.org/linux/man-pages/man2/PR_SET_TIMERSLACK.2const.html): scope and inheritance.
- [Linux v6.12 eventpoll.c](https://github.com/torvalds/linux/blob/v6.12/fs/eventpoll.c): ep_poll and schedule_hrtimeout_range.
- [Linux v6.12 timerfd.c](https://github.com/torvalds/linux/blob/v6.12/fs/timerfd.c): timerfd_setup and hrtimer_start.
- [Linux v6.12 select.c](https://github.com/torvalds/linux/blob/v6.12/fs/select.c#L36-L86): cap the timeout-derived estimate before taking the maximum with task slack.
- [Linux v7.1 select.c](https://github.com/torvalds/linux/blob/v7.1/fs/select.c): corroborating snapshot for the plugin correction.
- [signal](https://man7.org/linux/man-pages/man7/signal.7.html): masks, dispositions and standard-signal coalescing.
- [signalfd](https://man7.org/linux/man-pages/man2/signalfd.2.html): blocking watched signals and thread behavior.
- [OS jitter](https://docs.kernel.org/admin-guide/kernel-per-CPU-kthreads.html): interrupts, per-CPU work and housekeeping.
- [kernel parameters](https://docs.kernel.org/admin-guide/kernel-parameters.html): nohz_full and isolation limits.
