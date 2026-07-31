# Store write paths and forwarding geometry

Two focused experiments separate whole-line write allocation from dependent
store-to-load forwarding (STLF). The write comparison retains release
publication. Both experiments retain correctness checks, process isolation,
and fixed stopping as part of the measured contract.

## Whole-line publication

The write comparison overwrites a 4 KiB-aligned 512 MiB destination in complete
64-byte lines. Each arm writes the same eight-word pattern and ends by
release-publishing `ready = 1`.

- On x86-64, `A` uses aligned cacheable vector stores. `B` uses `VMOVNTDQ`,
  executes `SFENCE`, and then performs the release publication.
- On AArch64, `A` uses four `STP` instructions per line. `B` substitutes the
  advisory `STNP` hint. Both arms publish with a release store; the evidence
  gate requires manual confirmation of `STLR` in the final binary.

Setup allocates a second 512 MiB buffer. The scrub phase prefaults both buffers
and sweeps the second buffer before timing. Full destination verification and a
stronger same-thread fence occur after the timed publication boundary.

## Dependent forwarding

The STLF comparison runs 500,000,000 dependent iterations. Each iteration
stores eight bytes and feeds the following eight-byte load back into the next
store. `A` loads at the store address. `B` loads at `address + 4`, combining
four newly stored bytes with four unchanged fixture bytes. The scalar oracle
checks the final recurrence value outside the timed interval.

This loop measures latency along one dependency chain. It does not estimate
independent store or load throughput.

## Run

Run the correctness smoke checks from the workspace root:

```bash
cargo run -p topic-021-store-write-path --example store_path
cargo bench -p topic-021-store-write-path --bench write_path -- check
```

Run the retained Linux experiment from a clean checkout, with an empty output
directory outside the repository:

```bash
topics/021-store-write-path/experiment/run_remote.sh \
  "$PWD" /tmp/topic21-evidence 0
```

The remote runner builds one native binary, inspects its complete focused
functions, and executes 128 fresh pinned processes. See the [runner
contract](experiment/README.md), [measurement contract](measurements/README.md),
[first-round decision record](rounds/01.md), and [primary sources](references.md).

The first visit retains exact-source results for the [AArch64
host](measurements/2026-07-31-arm.md), [`xxl`
x86-64](measurements/2026-07-31-xxl.md), and the bounded [cross-host
interpretation](measurements/2026-07-31-cross-host.md).
