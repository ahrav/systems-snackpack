# Sources

Checked 2026-11-15 against the Linux man-pages project:

- [pidfd_open](https://man7.org/linux/man-pages/man2/pidfd_open.2.html): zombie retention, acquisition conditions, polling and close-on-exec.
- [clone3](https://man7.org/linux/man-pages/man2/clone.2.html): CLONE_PIDFD, clone_args and child creation.
- [pidfd_send_signal](https://man7.org/linux/man-pages/man2/pidfd_send_signal.2.html): stable signal target, permissions and ESRCH.
- [waitid](https://man7.org/linux/man-pages/man2/waitid.2.html): P_PIDFD, WNOWAIT, termination status and child ownership.

The example uses syscall macros from system headers for C portability across
AArch64 and x86-64. The native runs establish behavior on their recorded kernels.
