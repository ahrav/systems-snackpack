# Dirty-page tracking and snapshots with userfaultfd

Preserve each page before permitting its first write after the snapshot epoch.
Establish the epoch while application transactions are paused. A background
scanner and synchronous fault handler share one lock and saved flag per page.
The lock serializes copying, recording completion, and removing protection.

The Rust model checks 279,936 seven-operation histories against an eager copy.
The Linux C example uses populated private anonymous base pages, user-mode
faults, atomic bytes, fixed mappings, and disjoint writer ownership. Snapshot
storage and metadata stay outside the protected arena. Python independently
constructs every expected snapshot and final live byte.

```sh
cargo test -p userfaultfd-snapshot
cd topics/106-userfaultfd
cc -std=c11 -O2 -Wall -Wextra -Werror -pthread experiment/snapshot.c -o /tmp/topic106-snapshot
python3 experiment/check.py /tmp/topic106-snapshot
```

The checker starts 36 processes: 1/17/256 pages, 1/4 writers, 1/8 passes,
and pre-copy/fault-only/racing-scanner schedules. Each process has a 20-second
limit. Exit 77 records unavailable facilities; other failures fail the check.
Direct runs write `snapshot.bin` and `live.bin` in the current directory.

Protection is page-granular. Page events identify blocked attempts; they do
not count stores. Async dirty tracking requires its own consistency protocol.
Snapshot completion here means a volatile byte image. Durable recovery needs
separate persistence and commit rules. Repeated epochs, shared-page writers,
alias mappings, mapping changes, discard, fork, and kernel-originated accesses
need additional protocols and tests.

See [sources](SOURCES.md) and [results](rounds/01.md).
