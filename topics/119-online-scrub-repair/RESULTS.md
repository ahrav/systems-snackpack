# Repair correctness results

The conditional repair preserved the latest committed write on all three hosts. The unconditional repair restored old bytes. The generation-only control overwrote a recreated object at the same key.

| Platform | Kernel | Python | SQLite | Histories / post-event checks |
|---|---|---|---|---:|
| macOS arm64 | 25.6.0 | 3.13.16 | 3.54.0 | 864 / 3,456 |
| Linux AArch64 | 6.12.115-140.210.amzn2023.aarch64 | 3.9.25 | 3.40.0 | 864 / 3,456 |
| Linux x86-64 (xxl) | 6.12.115-140.210.amzn2023.x86_64 | 3.9.25 | 3.40.0 | 864 / 3,456 |

Each schedule contains one observation, one later installation and two ordered foreground actions. The six possible actions are a write of BLUE, a write of GOLD, recreation at generation 7, deletion, target damage and donor damage. Four initial states cover a damaged target, a healthy target, two bad copies, and missing authority. The product is 4 × 6² × 6 = 864 schedules. The final factor counts the choices of two scrub positions among four events. The oracle compares target bytes or absence and the repair row count after every event.

| Control | Observation on every host |
|---|---|
| Blind update after a foreground commit | One row changed. Generation 8 held BLUE and expected GOLD. |
| Successful version read, foreground commit, then blind update | The early check passed. The later update restored BLUE at generation 8. |
| Delete/recreate at generation 7 | The full token rejected the plan. Generation alone allowed BLUE to replace GOLD in the new incarnation. |
| SQLite write lock held through inspection and installation | The competitor with a zero lock timeout received a lock error. Retrying after commit installed GOLD. |

The test used two autocommit SQLite connections, WAL mode and fixed event order. Each host also passed four Python tests, two Rust unit tests and one Rust doctest. The threaded Rust test used channels to stop and resume the scrubber at a specific point. The immutable-bytes example used the repository's Rust 1.93.1 debug test profile.

The three hosts verified the same full Git archive for source `c06d2770757f81ff4249d285a84f7ec8271d46d9`, SHA-256 `58035b2b84dd55d55b2d45aa75b8b2c6348152481ed3693acf223f1ae263f545`. These are designed interleavings in a one-block model. Production filesystem repairs, power loss, repair latency, retry rates and lock wait distributions were outside the experiment.
