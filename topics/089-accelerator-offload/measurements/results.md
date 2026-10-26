# Topic 089 results: accelerator offload economics

Source commit: `116fbf3353c7ceebc7845c623589b90274289a97`.
Archive SHA-256: `4e7c5ba3c086d96ed342732f2eca6b28b391bab8283b98877fdbfc74e4fa035f`.
Both Linux hosts verified that identical archive before execution. Later commits
add evidence and prose; executable source remains identical.

## Correctness and validation

Five Rust unit tests, one doctest, 4,500 independent tick-simulation comparisons,
and 50 exact transform fixtures pass locally and on both Linux hosts. Every
timed workload's checksum also matches an independent Python integer oracle.
Zero-size inputs, zero rounds, zero-duration stages, invalid slots, time overflow,
engine serialization, dependencies, and buffer reuse are covered.

All six repository gates pass: formatting, workspace Clippy with warnings denied,
workspace library/binary/example tests, doctests, benchmark builds, and rustdoc
with warnings denied. Raw local logs remain in the standalone lesson bundle.

## CPU measurements

Each cell has ten fresh processes per variant, balanced five AB/five BA pairs.
Each process warms its preallocated buffers once. One CPU thread transforms
unchanged input to a complete output. Timing excludes allocation and checksum;
round-major includes its initial copy. Runs use CPU 0 from each host's allowed
set, Rust 1.93.1 / LLVM 21.1.8, default Cargo release settings, and no target-cpu
override. Repeat counts and raw totals are retained in CSV. Git copies use LF line
endings; original CRLF files remain in the standalone bundle. CSV fields are
identical, with both byte hashes retained in csv-normalization.json. Frequency, thermals,
SMT neighbors and host load remain uncontrolled. These are warm-buffer samples.

Arm: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`, Linux aarch64,
64 logical CPUs, ARM vendor, one thread/core, Amazon Linux kernel 6.12.111.
The lscpu output does not supply a marketing model name; its full fields are retained.

x86: SSH `xxl` resolves to `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`,
Linux x86_64, Intel Xeon Platinum 8488C, 192 logical CPUs, two threads/core,
Amazon Linux kernel 6.12.111. This verifies the requested x86-64 target.

Times below are median [minimum, maximum] microseconds per complete array.

| Host | Elements | Rounds | Element-major us | Round-major us | Winner |
|---|---:|---:|---:|---:|---|
| arm | 256 | 1 | 0.200 [0.199, 0.202] | 0.055 [0.055, 0.055] | round-major |
| arm | 256 | 32 | 5.434 [5.432, 5.478] | 1.175 [1.172, 1.180] | round-major |
| arm | 65,536 | 1 | 50.816 [50.440, 51.375] | 14.111 [14.011, 14.978] | round-major |
| arm | 65,536 | 32 | 1392.330 [1387.514, 1398.984] | 307.188 [306.127, 307.807] | round-major |
| arm | 1,048,576 | 1 | 807.130 [806.858, 876.573] | 297.729 [294.805, 305.008] | round-major |
| arm | 1,048,576 | 32 | 22353.637 [22251.511, 22446.868] | 4997.697 [4945.091, 5172.565] | round-major |
| xxl | 256 | 1 | 0.251 [0.249, 0.269] | 0.076 [0.075, 0.078] | round-major |
| xxl | 256 | 32 | 7.004 [6.985, 7.441] | 2.029 [2.000, 2.078] | round-major |
| xxl | 65,536 | 1 | 61.774 [61.455, 63.721] | 22.269 [22.017, 22.857] | round-major |
| xxl | 65,536 | 32 | 1794.951 [1784.964, 1822.175] | 530.265 [512.240, 537.652] | round-major |
| xxl | 1,048,576 | 1 | 988.992 [984.992, 1033.441] | 552.644 [549.291, 574.159] | round-major |
| xxl | 1,048,576 | 32 | 28720.591 [28688.444, 28888.252] | 8752.121 [8740.820, 8795.803] | round-major |

Round-major wins every cell under the declared rule: each of ten paired
comparisons favors it by more than 5%. This establishes the better tested CPU
baseline for these workloads and builds. It does not establish the fastest
possible CPU implementation or a population-level significance guarantee.
The proposed explanation is greater compiler-visible independence across
adjacent elements; this run collected neither disassembly nor PMU evidence
for that mechanism, so attribution remains an inference.

## Model results and accelerator limits

With assumed H2D/compute/D2H durations 4/2/4, eight batches finish at 80, 44 and
38 time units using one, two and three buffer slots. This deterministic model
assumes three independent engines, FIFO order, ready input, zero launch cost,
and slot retention through D2H. Its results have no hardware timing variability.
The two linear crossover examples use explicitly invented coefficients.

Both Linux hosts lack nvcc, nvidia-smi, /dev/nvidia0, /dev/nvidiactl and /dev/dri.
Local Metal device discovery returned null twice. Device execution could not
be tested. GPU correctness, kernel and end-to-end timings, timing variability,
CPU/device crossover, energy and monetary cost remain unmeasured. CPU numbers
must not be presented as accelerator performance.

Concrete remaining measurement: on an authorized accelerator host, implement
the same integer contract, verify every output against the retained Python
oracle, then measure CPU, one-shot offload and resident/overlapped variants
with matching input/output boundaries and balanced process trials. Record
cold setup, transfers, memory budget, stage and end-to-end timings, arrival
and batch-deadline behavior, and variability. Pin any added device source in
a new commit before that campaign. Today's CPU source is already retained.

## Plugin finding

A scoped audit of ahrav-claude-plugins origin/main at
`5cfc97c1fa89cff560a527a1f3e502309e4cd9a1` found existing coverage for this
lesson's transfer accounting, residency, timelines, buffer completion, queue
limits and model assumptions. No skill changed; no plugin PR or model-based
skill evaluation is required for this run. The standalone bundle retains the
owner/path audit. Historical evaluation follow-ups remain separate.
