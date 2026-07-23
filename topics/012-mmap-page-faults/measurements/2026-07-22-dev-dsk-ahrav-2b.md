# 2026-07-22 AArch64 host record

The run used source commit `bdd17c6947fbf66207e4bf7204a786d996bad83b`
and archive SHA-256
`74738647fce356a0db4e6901f668ea5cb956778030bbc8300187057c16d5a83b`.
The executing driver and the driver extracted from that archive both had
SHA-256 `d439df3df286dbce573f5e2b09eb3df6d5cb76079dec527dd01baacbe26e35c6`.

## Host boundary

| Field | Observed value |
| --- | --- |
| Requested and resolved host | `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com` |
| Kernel | `6.12.94-123.180.amzn2023.aarch64` |
| CPU | ARM implementer `0x41`, architecture `8`, part `0xd40`, stepping `r1p1` |
| Online CPUs and NUMA | 64 CPUs, one NUMA node, automatic NUMA balancing disabled |
| Base page and THP | 4,096 bytes; THP enabled policy `madvise`; workload used `MADV_NOHUGEPAGE` |
| Memory and swap at probe | 129,541,096 KiB total; 93,519,660 KiB available; no swap |
| File path | `/local/home/ahrav`, XFS on `/dev/nvme0n1p1` |
| C compiler | GCC 11.5.0 with `-O3 -std=c11 -Wall -Wextra -Werror -fno-omit-frame-pointer -march=native` |
| Rust toolchain | rustc 1.93.1, LLVM 21.1.8; Cargo 1.93.1 |
| Rust build flags | `-C target-cpu=native -C debuginfo=1 -C codegen-units=1` |

The host exposed ASIMD, SVE, atomics, SVE i8mm, and SVE bf16 among its CPU
features. Clang was not installed. The [raw host record](raw/bdd17c6/arm/host-env.txt)
contains the complete feature and mount output.

## Process results

Each mode used eight fresh CPU-0-pinned processes. `CLOCK_MONOTONIC_RAW`
covered only one volatile byte touch per runtime base page. The setup interval
started inside the workload process and ended before the touch loop. A Python
monotonic boundary covered the complete pinned workload subprocess.

| Mode | Touch median | Mean ± sample SD | Range | Setup median | Fault delta in every process |
| --- | ---: | ---: | ---: | ---: | --- |
| Anonymous first write | 8.782741 ms | 8.758056 ± 0.458700 ms | 7.766355–9.313856 ms | 0.037932 ms | 8,192 minor; 0 major |
| Anonymous read after `MADV_DONTNEED` | 2.839449 ms | 2.851634 ± 0.029794 ms | 2.823500–2.902666 ms | 10.847123 ms | 8,192 minor; 0 major |
| Resident cached file | 0.428283 ms | 0.426252 ± 0.005926 ms | 0.417828–0.432814 ms | 37.591129 ms | 512 minor; 0 major |
| Verified nonresident file | 4,629.673715 ms | 4,630.332872 ± 3.235330 ms | 4,624.494803–4,635.898092 ms | 22.292791 ms | 0 minor; 8,192 major |

Every file-cold process moved from `0/8192` resident pages to `8192/8192`.
Every file-warm process started and ended `8192/8192` resident. The paired
cold/warm touch ratio had median `10,820.732228×`, sample standard deviation
`153.244455×`, and range `10,684.716305–11,080.352004×`. These values describe
the eight process blocks, not independent pages or a confidence interval.

The anonymous modes have equal fault counts but different operations. First
write allocates writable memory. The refault mode reads discarded private pages
and can map the shared zero page. Their ratio is not a speedup measurement.

## Correctness and generated code

All workspace gates passed in the extracted source tree. The exact example
printed `validated cold-file evidence and eight-block schedule`. The portable
Rust benchmark ran 5,000,000 pairs of derived-metric calculations in
27,613,306 ns; that boundary does not exercise `mmap` or Linux page faults.

The linked C read loop uses `ldrb`, advances by the runtime page stride, and
accumulates the byte. The linked write loop uses `strb`, advances by the runtime
stride, and accumulates its deterministic value. These instructions prove the
compiler retained the sparse volatile accesses. They do not identify PTE,
residency, or fault state.

Raw process rows, summaries, gates, manifests, source verification, disassembly,
and bundle checksums are under [the Arm evidence directory](raw/bdd17c6/arm/).
