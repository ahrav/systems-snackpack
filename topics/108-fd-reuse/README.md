# File-descriptor reuse races

Resolve delayed work with a slot and generation while holding ownership through
I/O. A recycled descriptor number can name a different connection.

`Registry` models identity checks with a single owner. The caller owns the OS
resource, serializes validation through I/O with retirement, marks the slot dead,
deregisters the old epoll key, then closes once. Worker commands carry tokens.
A handler that yields revalidates after resumption. Exhausted generations retire
the slot permanently. Copying the returned integer grants no lifetime extension.

```sh
cargo +1.93.1 test -p topic108-fd-reuse
cargo +1.93.1 run --release -p topic108-fd-reuse --example oracle
python3 topics/108-fd-reuse/examples/reuse.py
cc -std=c11 -O2 -Wall -Wextra -Werror topics/108-fd-reuse/native/epoll_reuse.c -o /tmp/topic108-epoll
/tmp/topic108-epoll
```

The C commands require Linux. The Python program runs in an isolated process and
forces descriptor reuse. Expect a rejected stale token and a raw callback that
consumes B. The native test captures a real event, forces reuse, compares data
bytes from distinct pipes, and checks all four duplicate/deregister combinations.

The independent oracle tracks unique connection identities in a separate ledger.
It compares every retained token after each operation in all 65,536 eight-action
histories over two slots. Oracle decisions use identity equality, without unpacking
or generating a generation. Each successful insertion also queues a delayed token.
Repeated lookup models arbitrarily delayed callbacks within the bounded history.

## Selection

| Method | Appropriate scope | Cost |
|---|---|---|
| Owner thread plus tokens | Nonblocking event-loop operations | Serialized dispatch and command queues |
| Lock through validation/use | Short shared operations | Contention and retirement delay |
| Duplicate under ownership lock | Keep the old kernel object alive during work | Descriptor/syscall cost; shared stream/offset coordination |
| Defer close until callbacks finish | Existing lifetime tracking | Memory/fd retention and queue/timer accounting |

A standalone generation check has a check/use race if another thread can close
the fd before I/O. Pointer tokens require allocation lifetime protection before
lookup. A 32-bit generation wraps after about 71.6 minutes at one million reuses
per second. This arithmetic motivates explicit exhaustion behavior.

`EPOLL_CTL_DEL` removes the interest entry; copied userspace events remain.
Aliases can preserve the old registration after close. `EPOLLONESHOT` controls
rearming. Applications still own callback identity and lifetime. Valid readiness
requires nonblocking error handling, including `EAGAIN`.

Results and scope appear in [RESULTS.md](RESULTS.md); sources in [SOURCES.md](SOURCES.md).
