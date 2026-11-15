# Race-free process supervision with pidfd

Retain a process identity from creation through cancellation and reaping.
`Processes` models two reusable numeric PIDs and stable birth identities.
The single owner creates, exits, reaps, and signals processes. Signals in this
model select running targets; zombie syscall return behavior is outside its scope.

Run from the repository root:

```sh
cargo +1.93.1 test -p topic109-pidfd
cargo +1.93.1 run --release -p topic109-pidfd --example oracle
python3 topics/109-pidfd/examples/demo.py
cc -std=c11 -O2 -Wall -Wextra -Werror topics/109-pidfd/native/supervise.c -o /tmp/topic109-supervise
/tmp/topic109-supervise
```

The Python and C programs require Linux. Run the Python example without
optimization, because assertions validate its observations. The C checks remain
active with `-DNDEBUG`. Expect the Python PASS line and four native counts of 64.
An explicit clone3 limitation means the two atomic-creation cases were skipped.

The oracle exhausts 279,936 seven-action histories over two numeric PIDs. It retains
independent reference-counted objects, marks their live flags on exit, and releases
PID slots on reap. Retained oracle references remain attached to those objects.
Every retained implementation handle is checked after every action. The raw-PID
negative control must select wrong identities in some histories.

The native program repeats four cases 64 times: clone3 with pidfd-directed SIGTERM,
fork/open with SIGTERM, fork/immediate exit followed by zombie acquisition,
and clone3/immediate exit. Each checks CLOEXEC, exit readiness, child identity,
termination cause, WNOWAIT status retention, reaping, ESRCH after reaping, and
ECHILD after status consumption. A single-threaded parent owns all reaping.
Only the running cases check initial unreadiness. Poll retries use an absolute
monotonic deadline. The outer runner supplies a process deadline for blocking waits.

## Ownership and selection

`clone3(CLONE_PIDFD)` acquires identity during creation. `fork()` followed by
`pidfd_open()` requires default SIGCHLD handling, absence of SA_NOCLDWAIT, and
exclusive reaping until acquisition. An exited unreaped child retains its PID.
An arbitrary PID looked up after its original process was reaped can identify a
replacement process. A successful open stabilizes the process selected then.

Poll readiness reports exit; `waitid(P_PIDFD)` consumes a waitable child's status.
WNOWAIT supports observation before consumption. A pidfd for an unrelated process
provides identity but does not confer parenthood or general reaping authority.
Deregister and retire callbacks before close. The pidfd descriptor number itself
can be reused, so ownership must cover lookup through signaling or waiting.

| Choice | Suitable scope | Cost or condition |
|---|---|---|
| waitpid and numeric PID | Exclusive child-lifetime owner | Retire cancellation before reaping permits reuse |
| SIGCHLD/signalfd | Central Linux exit collection | Per-thread masks and draining waitable children |
| fork and pidfd_open | Parent controls all reaping | Extra syscall and descriptor per child |
| clone3 with CLONE_PIDFD | Atomic child identity acquisition | Linux kernel and sandbox support |

Signal delivery preserves permissions. SIGTERM may be handled or ignored; confirm
exit and keep the same pidfd for any escalation. Distinguish EPERM, ESRCH,
unsupported APIs, and fd exhaustion. Descendant cleanup needs a separate policy.

See [sources](SOURCES.md) and [results](RESULTS.md).
