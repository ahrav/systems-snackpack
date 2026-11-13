# Primary sources

Read 2026-11-12. Runtime capability checks determine support on the tested hosts.

- [Linux 6.12 userfaultfd documentation](https://docs.kernel.org/6.12/admin-guide/mm/userfaultfd.html): synchronous and asynchronous WP, anonymous empty PTEs, capability negotiation, mapping lifecycle.
- [userfaultfd syscall](https://man7.org/linux/man-pages/man2/userfaultfd.2.html): user-mode-only faults and descriptor lifecycle.
- [UFFDIO_REGISTER](https://man7.org/linux/man-pages/man2/UFFDIO_REGISTER.2const.html): registration and returned range capabilities.
- [UFFDIO_WRITEPROTECT](https://man7.org/linux/man-pages/man2/UFFDIO_WRITEPROTECT.2const.html): aligned protection, unprotection and wakeup semantics.

The epoch protocol, eager-copy oracle, and fixed-mapping restrictions are this
example's design. The tests establish the declared byte-image property under
those restrictions. Performance and production checkpoint latency require
separate measurements.
