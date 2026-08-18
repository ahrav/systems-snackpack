# Zero-copy and its limits

Moving bytes costs memory bandwidth, processor time, system calls, and buffer
space. Linux can avoid a particular copy, but no interface makes all movement
free. The useful question is therefore not “is this zero-copy?” It is “which
copy disappears, what new ownership rule appears, and does the complete path
improve?”

This topic models those decisions and measures one narrow file-to-socket case.
It is not a general ranking of Linux networking interfaces.

## Start with the path, not the API name

Use one running example throughout this note:

- A server sends a cached 64-mebibyte (MiB) file. One MiB is 1,048,576 bytes.
- It also sometimes sends a generated 1 MiB application buffer.
- File operations request 1 MiB at a time.
- The machine uses 4-kibibyte (KiB) virtual-memory pages. One KiB is 1,024
  bytes.

For every candidate, write down three things:

1. **Location:** Where are the bytes before and after each stage?
2. **Ownership:** Which layer may change or free that storage?
3. **Completion:** Which event means the storage can be reused?

The baseline file path calls `pread` to copy page-cache bytes into an
application buffer, then calls `send` to copy those bytes into kernel socket
storage. `pread` reads at an explicit file offset. `send` submits an
application buffer to a socket. This names two 64 MiB payload copies. It does
not count storage reads, protocol headers, checksums, receiver work, or device
movement.

“Zero-copy” is shorthand for avoiding one named copy inside such a boundary.
Direct memory access (DMA) means that a device moves bytes without the central
processing unit (CPU) executing a load and store for each byte. DMA still moves
the bytes and can still consume memory and interconnect bandwidth.

## What each technique solves

| Technique | What problem does it solve? | How does it work? | What does it not solve? | Main catch | Choose it when |
| --- | --- | --- | --- | --- | --- |
| `pread` plus `send` | Provides a portable, inspectable baseline and lets the application transform bytes | Copies file bytes into an application buffer, then submits that buffer | It does not avoid either named payload copy | Two copies consume CPU and memory bandwidth; both calls can make short progress | The application must parse, transform, encrypt, or retain the bytes, or the simpler path is already fast enough |
| `sendfile` | Avoids bringing unchanged file bytes through an application buffer | The kernel connects a file description directly to a socket description | It does not promise device-level zero-copy, delivery, or support for every input/output pair | Calls can return short progress; unsupported combinations need a tested fallback; shared pages must remain unchanged until consumed | A regular file is already cached and its bytes can go unchanged to a socket |
| `splice` | Connects two kernel objects while exposing a pipe as the handoff boundary | One call places page references in a pipe and another drains the pipe to a socket | It does not remove the pipe, make endpoints nonblocking, or guarantee that requested pages move | At least one endpoint must be a pipe; capacity and partial progress can multiply calls; `SPLICE_F_MOVE` is currently only a hint with no effect | A pipeline already uses pipes or must connect several compatible kernel endpoints |
| `MSG_ZEROCOPY` | Avoids copying large generated application buffers into socket storage | After enabling `SO_ZEROCOPY`, a send with the `MSG_ZEROCOPY` flag may hold the application's pages until an error-queue completion | It does not prove remote delivery, prevent a copied fallback, or make a small send cheap | The buffer must remain unchanged until its inclusive completion range arrives; notifications can coalesce, reorder, and wrap 32-bit identifiers; resource pressure can fail a send | Large generated buffers are immutable long enough and the application already owns completion bookkeeping and backpressure |

`SO_ZEROCOPY` is the socket option that enables later zero-copy requests.
`MSG_ZEROCOPY` is the per-send Linux message flag. The socket error queue is a
separate queue used here for asynchronous lifetime notifications. A successful,
nonempty flagged send consumes one 32-bit identifier. A completion range is
inclusive: `[first, last]` completes both endpoints and every submitted
identifier between them. The kernel may report that it copied the data after
all; that fallback still produces the lifetime completion.

No method removes ordinary correctness work. Loop until the requested length
is sent, handle interruption, preserve file offsets deliberately, bound queues,
and define what happens after a partial failure. A zero return before completion
needs an explicit policy rather than an infinite loop.

## Cost screens before measurement

The first screen asks how many bytes cross the named application boundary. It
does not predict elapsed time. If `S` is the logical size and `P` is the number
of complete named copy passes, then:

```text
named_copy_bytes = S * P
```

For the 64 MiB file, the baseline has `P = 2`, so `64 MiB * 2 = 128 MiB`.
`sendfile` and `splice` have `P = 0` at this named boundary, so the result is
zero here. In plain language: they avoid 128 MiB of application-boundary copies,
not every movement in the system.

The checked Rust model adds a deliberately simple time screen. Let `C` be the
effective bandwidth of only the named copies, `N` the call count, `F` a fixed
cost per call, and `O` other serial cost supplied by the caller:

```text
copy_ns = ceil((S * P) * 1,000,000,000 / C)
screened_time_ns = copy_ns + N * F + O
```

For a worked input, use `C = 20 GiB/s`, where one gibibyte (GiB) is
1,073,741,824 bytes, and `F = 200 ns`, where a nanosecond (ns) is one billionth
of a second. The baseline requests 64 chunks through each of two calls, so
`N = 128`: copy time is `128 MiB / 20 GiB/s = 6.25 ms`, call time is
`128 * 200 ns = 25.6 microseconds`, and the result is `6.2756 ms`. A one-call
per chunk candidate with `P = 0`, `N = 64`, and `O = 0` screens at
`64 * 200 ns = 12.8 microseconds`. In plain language: the assumptions make
copy avoidance look attractive, but omitted kernel and network costs make this
a candidate filter, not a forecast.

An explicit pipe adds a separate capacity question. If `Q` is pipe capacity
and `K` is the requested chunk, one fill-and-drain cycle can move no more than
the smaller value:

```text
cycles = ceil(S / min(Q, K))
minimum_splice_calls = 2 * cycles
```

For the 64 MiB file, a 64 KiB pipe and a 1 MiB request give
`min(64 KiB, 1 MiB) = 64 KiB`, then `64 MiB / 64 KiB = 1,024` cycles and at
least `2 * 1,024 = 2,048` `splice` calls. In plain language: a large requested
chunk does not override a smaller pipe, and short progress can add more calls.

Application-backed zero-copy adds a page-lifetime question. For an aligned
range, page count is the byte length divided upward by page size. An unaligned
range can touch one more page. The exact half-open-range calculation is:

```text
pages = floor((offset + length - 1) / page_size)
        - floor(offset / page_size) + 1
```

For the generated 1 MiB buffer at offset zero with 4 KiB pages, this is
`floor((1,048,576 - 1) / 4,096) - 0 + 1 = 256` pages. At offset one it is
`floor(1,048,576 / 4,096) - 0 + 1 = 257` pages. In plain language: alignment
changes the page-accounting surface even when the payload length does not
change.

Finally, delayed completion retains memory. Let `lambda` be successful sends
per second, `B` bytes retained per send, and `L` mean completion latency in
seconds:

```text
average_held_bytes = lambda * B * L
```

At 20,000 sends per second, 64 KiB per send, and 5 milliseconds mean completion
latency, the average is `20,000 * 65,536 * 0.005 = 6,553,600` bytes, or
6.25 MiB. At 100 milliseconds it becomes 125 MiB. In plain language: a path
that saves copy time can create a large outstanding-memory obligation when
completion slows. A mean is not a tail bound, so admission must also cover
slow completions.

Run the checked examples with:

```bash
cargo run --locked --package zero-copy-limits \
  --bin zero-copy-contract-probe -- verify
cargo run --locked --package zero-copy-limits \
  --bin zero-copy-contract-probe -- model
```

## Failure modes and advice that breaks down

- **“The API is zero-copy, so CPU use should vanish.”** Protocol processing,
  checksums, page-reference work, encryption, receiver copies, completion work,
  and cache effects remain.
- **“Fewer bytes copied always means lower elapsed time.”** Setup, more system
  calls, pipe capacity, pinning, notifications, short progress, and contention
  can dominate. Measure the full treatment and its CPU split.
- **“A successful send means the buffer is reusable.”** That is true for an
  ordinary copying send after the call returns, but false for `MSG_ZEROCOPY`.
  Reuse only after the corresponding validated completion.
- **“Completion means delivery.”** It means that local storage may be reused.
  Delivery and application acknowledgment are separate contracts.
- **“The nonblocking flag prevents blocking.”** `SPLICE_F_NONBLOCK` applies to
  pipe operations. The other file description can still block.
- **“`sendfile` works for every file and socket.”** File-description types,
  kernel version, filesystem behavior, and output restrictions matter. Keep a
  correctness-tested buffered fallback for expected unsupported errors.
- **“Transport Layer Security preserves the same path.”** Transport Layer
  Security (TLS) encrypts records. Kernel TLS in software creates encrypted
  output buffers. Direct file-page transmission requires compatible device
  offload and its separate immutable-source contract.
- **“Loopback proves network-interface behavior.”** Linux loopback is a local
  software path. Current kernel documentation says `MSG_ZEROCOPY` always
  reports copied fallback on loopback. It cannot establish network interface
  card (NIC), DMA, or remote-host behavior.

## Retained two-host observation

The retained run asks one narrow question: for a prewarmed 512 MiB file in
memory-backed temporary storage, how did three file-to-loopback-socket paths
compare on two named Linux machines? It does not test storage misses, a network
interface card (NIC), direct memory access (DMA), a remote receiver, Transport
Layer Security (TLS), congestion, production concurrency, or `MSG_ZEROCOPY`
performance. Each process performed one transfer. Eight paired,
order-balanced four-period blocks were the replication units. Inner receiver
calls were not counted as independent samples.

Both hosts ran source commit
`c6b76b4429272814c7e3ab57a199c9d2c2d8ce66` from an archive with Secure Hash
Algorithm 256-bit (SHA-256) digest
`f6e75b525d82964437d23f74494758ccdddd1bc0da31e3b2971cdf4d9cd913e4`.
SHA-256 is a content digest used here to identify exact bytes. The Arm result
archive has digest
`dcea29d8131846a50fd1f3da3a9efa618a0a0068d953bfd4734b9f159a494877`;
the `xxl` result archive has digest
`7403a907c3dd5f882b7dc77bdd8b977ef2571b784db3cd830a0fcff60592d995`.
The later evidence-only commit retains those archives and this prose without
changing the measured experiment source.

The point estimate is the geometric mean of complete-block log ratios. A
95-percent confidence interval (CI) is the Student-t working-model interval
for those eight process-block contrasts. Standard deviation (SD) is the sample
SD of those log contrasts. These derived summaries describe variation in this
one sequential run under approximate independence and normality assumptions;
they are not prediction intervals for another host or run. `A/A` means both
labels executed the buffered method and checks scheduling and analysis
plumbing.

| Host and pair; ratio is B / A | Ratio | 95% CI | SD | Median A / B |
| --- | ---: | ---: | ---: | ---: |
| Arm host; buffered A, `sendfile` B | 0.535180981 | [0.528409683, 0.542039049] | 0.015228149 | 0.185384020 s / 0.099415578 s |
| Arm host; buffered A, `splice` B | 0.538883052 | [0.536157533, 0.541622426] | 0.006064140 | 0.184253430 s / 0.099232702 s |
| Arm host; buffered A, buffered B | 1.000467926 | [0.996529935, 1.004421478] | 0.004716735 | 0.184354762 s / 0.183927217 s |
| `xxl` host; buffered A, `sendfile` B | 0.682472664 | [0.668834195, 0.696389240] | 0.024141832 | 0.141917248 s / 0.096720350 s |
| `xxl` host; buffered A, `splice` B | 0.676646220 | [0.669328562, 0.684043880] | 0.013004189 | 0.141660406 s / 0.095911539 s |
| `xxl` host; buffered A, buffered B | 0.994674852 | [0.989507348, 0.999869343] | 0.006229370 | 0.144373092 s / 0.144179088 s |

The Arm A/A interval includes 1. The `xxl` A/A interval narrowly excludes 1
under this working model. That small result exposes residual label, order, or
run asymmetry; it is not a calibrated noise correction for the candidate
ratios. The candidate effects are much larger, but the asymmetric treatment
still prevents attributing them only to payload-copy removal.

The exact Arm identity was
`dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, `aarch64`, Linux
`6.12.95-124.187.amzn2023.aarch64`, 64 available CPUs, MIDR implementer
`0x41` and part `0xd40`, GCC 11.5.0, and Rust 1.95.0. Secure Shell (SSH) alias
`xxl` resolved at run time to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, `x86_64`, Linux
`6.12.95-124.187.amzn2023.x86_64`, Intel Xeon Platinum 8488C under KVM, 192
available CPUs, GCC 11.5.0, and Rust 1.97.1. KVM means Kernel-based Virtual
Machine. The host notes retain exact toolchain, build-flag, executable, elapsed,
and central processing unit (CPU) identities and medians.

All 96 timing processes per host returned success. Separate exact-byte checks
sent 16,777,219 bytes through every method. The requested chunk was 256 KiB;
the observed pipe capacity was 64 KiB. The measured transfer C source had
SHA-256 digest
`3aa13f0ea4701617cfba297986404e3e44bdec37e6d2294f2ef913237eeafd16`.

The `transfer_sec` treatment deliberately includes allocation and release of
the buffered path's application buffer and creation and close of the `splice`
pipe. It starts after the sender has opened the file and connected its socket,
but there is no separate receiver-ready barrier, so receiver `accept` and
buffer allocation can overlap the beginning. It ends only after sender
shutdown, receipt of the receiver report, and child-process exit. Those
method-specific setup choices and endpoint-lifetime costs are part of the
asymmetric treatment. Sender CPU covers this interval; receiver CPU covers the
child's whole lifetime. The runner also records `setup_sec`, `total_sec`, and
outer process time. Do not attribute the elapsed ratios solely to removed
payload copies.

The generated-code check observed linked call sites for `pread`, `send`,
`sendfile`, and two `splice` calls in generic and native executables on both
machines. This proves that the executables contain the intended external call
sites. It does not prove which path executed, which kernel path handled it, or
why timings differ. The separate generic and native `MSG_ZEROCOPY` controls
sent eight aligned 64 KiB buffers, verified all 524,288 bytes, held storage
until identifiers 0 through 7 completed, and observed copied fallback on
loopback on both hosts. These were correctness and lifetime controls only; no
timing was reported. Strict call-site receipts contained exactly five transfer
calls and three completion-control calls for each generic and native executable
on each host.

Both validators passed. The source manifests before and after each run were
byte-identical: each listed 1,773 source entries and had SHA-256 digest
`0b2ceed67acaf154b8aaf1bbf75d05f629c1b39d279dc003555cc3690b222688`.
The validators also recomputed the retained analyses exactly and checked that
each zero-copy completion's `ee_code` agreed with its copied-fallback field.
After retrieval, both archive digests matched, and every one of the 272 entries
in each internal result manifest verified. Raw process times,
byte counts, completed non-`EINTR` operation counts, CPU intervals, completion
records, metadata, hashes, and call sites are measured. `EINTR` means a system
call was interrupted before normal completion; the counters omit those retried
attempts. Ratios, medians, SDs, and CIs are derived. Copy, cache,
page-reference, protocol, and scheduler explanations remain inferred. The
observations describe only the named machines; they do not establish a property
of Arm or x86-64 processors.

## Focused Linux experiment

The checked-in experiment reproduces the retained treatment. It compares
buffered `pread` plus `send`, `sendfile`, and `splice` over the same generated
file and an Internet Protocol version 4 (IPv4) loopback Transmission Control
Protocol (TCP) connection. IPv4 is the 32-bit Internet address format; TCP is
the reliable byte-stream transport. The correctness run checks every received
byte. Timing runs avoid the per-byte comparator but still require the exact byte
count and clean receiver status.

On Linux, choose two CPUs allowed by the current process, replace `0,1` below
if necessary, and use output paths that do not exist:

```bash
bash topics/038-zero-copy-limits/experiment/build_probe.sh \
  /tmp/topic038-build

python3 -B -I topics/038-zero-copy-limits/experiment/run_processes.py \
  --binary /tmp/topic038-build/transfer-probe-native \
  --payload /dev/shm/topic038-payload \
  --output /tmp/topic038-results \
  --cpu-list 0,1

python3 -B -I topics/038-zero-copy-limits/experiment/analyze.py \
  /tmp/topic038-results/runs.tsv \
  --summary /tmp/topic038-results/summary.tsv \
  --contrasts /tmp/topic038-results/contrasts.tsv

/tmp/topic038-build/msgzc-control \
  > /tmp/topic038-results/msgzc-generic.stdout
/tmp/topic038-build/msgzc-control-native \
  > /tmp/topic038-results/msgzc-native.stdout

python3 -B -I topics/038-zero-copy-limits/experiment/validate_receipts.py \
  /tmp/topic038-results \
  --binary /tmp/topic038-build/transfer-probe-native

objdump -drwC /tmp/topic038-build/transfer-probe-native \
  > /tmp/topic038-results/transfer-native.disassembly
objdump -drwC /tmp/topic038-build/msgzc-control-native \
  > /tmp/topic038-results/msgzc-native.disassembly
rg -n '\b(callq?|bl)\b.*<(pread|send|sendfile|splice)@' \
  /tmp/topic038-results/transfer-native.disassembly
rg -n '\b(callq?|bl)\b.*<(setsockopt|sendmsg|recvmsg)@' \
  /tmp/topic038-results/msgzc-native.disassembly
```

Expected observations:

- three exact-byte correctness processes pass;
- 96 fresh timing processes form eight `ABBA` or `BAAB` blocks for each of
  buffered-versus-`sendfile`, buffered-versus-`splice`, and buffered A/A;
- the validator prints `VALIDATION=PASS` only after checking raw-output hashes,
  schedule, process results, analyses, and both completion controls;
- `MSG_ZEROCOPY` loopback reports full completion coverage and can report the
  documented copied fallback; and
- the final `objdump` and `rg` commands show linked external call instructions,
  but do not identify shared-library or kernel internals.

Important controls are a prewarmed immutable payload, equal logical bytes and
requested chunks, exact-byte correctness outside timing, fresh processes,
paired order balance, a buffered A/A path, no retry, sender and receiver CPU
accounting, separate process-outer time, exact source and executable hashes,
and both generic and native correctness builds. See
[`rounds/01.md`](rounds/01.md) for the promotion contract and
[`measurements/README.md`](measurements/README.md) for retained-evidence rules.

## Practical selection guide

1. Name the exact copy and workload stage you want to remove.
2. Keep buffered I/O as the correctness comparator and expected fallback.
3. Choose `sendfile` for unchanged file-to-socket bytes.
4. Choose `splice` when an explicit bounded pipe is part of the architecture,
   not merely because its name suggests zero-copy.
5. Choose `MSG_ZEROCOPY` for large generated buffers only after implementing
   per-socket identifiers, inclusive completion ranges, wrap, copied fallback,
   memory admission, and shutdown cleanup.
6. Test TLS, storage, device, and remote-receiver configurations separately.
7. Measure elapsed time, sender and receiver CPU, call counts, outstanding
   memory, completion delay, fallback rate, and slow requests.

The central rule is simple: copy avoidance changes a contract. Select the path
whose ownership and completion rules the service can uphold, then keep it only
when the complete measured workload improves.
