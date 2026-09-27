# Source ledger

Accessed 2026-09-27. The executable counter is an original finite model. These
sources support the testing distinctions, not the experiment's numeric results.

| Primary source | Version or scope | Supported distinction |
| --- | --- | --- |
| [FoundationDB simulation and testing](https://apple.github.io/foundationdb/testing.html) | Documentation 7.4.8 | Deterministic simulation runs a cluster in one thread; live performance and hardware failure tests provide separate evidence. |
| [Loom crate documentation](https://docs.rs/loom/0.7.2/loom/) | Loom 0.7.2 | Concurrency operations require instrumentation; preemption bounds restrict the search; relaxed-memory modeling has documented limitations. |
| [Loom model builder](https://docs.rs/loom/0.7.2/loom/model/struct.Builder.html) | Loom 0.7.2 | Branch, permutation, duration, and preemption settings constrain different aspects of exploration. This artifact does not execute Loom. |
| [Specifying Systems](https://lamport.azurewebsites.net/tla/book-02-08-08.pdf) | Lamport, 2002; chapters 7, 8, 14 | Atomicity belongs to the specification; fairness is an explicit progress assumption; finite model checking has model boundaries. This artifact does not execute TLC. |

Do not infer full program correctness, liveness under arbitrary scheduling,
hardware-memory coverage, or performance from this model's exhausted trace tree.
