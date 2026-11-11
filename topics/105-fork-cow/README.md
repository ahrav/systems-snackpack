# Fork copy-on-write amplification

Count distinct shared pages written while a snapshot child retains them.
The Rust model counts first writes. Its independent byte-history oracle checks
32,768 histories and 163,840 prefixes. The C experiment compares packed flags
with one flag per base page, with identical logical results.

```bash
cargo test -p fork-cow
python3 topics/105-fork-cow/snapshot.py
cd topics/105-fork-cow
cc -O2 -std=c11 -Wall -Wextra -Werror native.c -o /tmp/topic105-cow
python3 run.py /tmp/topic105-cow > /tmp/topic105-results.json
```

The native experiment requires Linux `/proc` and `MADV_NOHUGEPAGE` support.
It creates a guarded populated private mapping and retains the child until both
memory samples finish. Parent and child full-byte checks run outside timing.
The Python oracle checks mapping RSS, summed PSS growth, private dirty bytes,
zero swap and zero observed PMD THP. The successful NOHUGEPAGE advice controls
all transparent huge-page sizes for the mapping.

Each host runs eight alternating-order pairs for each of four workloads:
1,024/4,096 flags, one/eight write passes. One warmup pair precedes each cell.
Every sample uses a fresh process. Linux processes share one permitted CPU.
Repeated volatile stores preserve repeated work. Mutation time excludes setup,
fork, memory sampling, validation and child teardown. Fork return time is
recorded separately. Minor faults cover the parent process and include possible
non-mapping faults; memory conclusions use isolated mapping counters.

The flag layouts represent mutable metadata placement. Real allocator free
paths, database snapshots, huge pages and disk durability require separate
experiments. See [sources](SOURCES.md) and [results](rounds/01.md).
