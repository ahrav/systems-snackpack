# Primary sources

Accessed 2026-11-14.

- [epoll(7)](https://man7.org/linux/man-pages/man7/epoll.7.html): registration key,
  descriptor aliases, event-cache pitfalls, readiness and oneshot behavior.
- [epoll_ctl(2)](https://man7.org/linux/man-pages/man2/epoll_ctl.2.html): ADD/DEL and
  application data returned with events.
- [close(2)](https://man7.org/linux/man-pages/man2/close.2.html): descriptor reuse,
  in-flight Linux operations and close-error handling. Linux close error behavior
  differs from the POSIX.1-2024 EINTR requirement; follow the deployed platform.
- [dup(2)](https://man7.org/linux/man-pages/man2/dup.2.html): aliases share the open
  file description; dup2 atomically replaces a destination descriptor.
- [Linux file management](https://docs.kernel.org/filesystems/files.html): kernel
  descriptor-table lookup and file reference lifetimes. Kernel RCU rules are
  distinct from this application's single-owner protocol.
