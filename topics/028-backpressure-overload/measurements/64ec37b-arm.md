# Arm exact-source result: `64ec37b`

The required Arm host completed the full Topic 28 protocol from source commit
`64ec37b944051279f71c3af32de050b94f7d824e`. All workspace, source-stability,
code-generation, schedule, semantic-control, raw-receipt, analysis, and evidence
manifest gates passed.

## Host and artifact

- Host: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Architecture: `aarch64`; Arm implementer `0x41`, part `0xd40`, revision `r1p1`
- Kernel: `6.12.94-123.192.amzn2023.aarch64`
- CPUs: 64 available; every calibration and treatment process used CPUs `0,1,2,3`
- Clock source: `arch_sys_counter`
- Toolchain used after the controlled environment sweep: rustc/Cargo `1.93.1`, LLVM `21.1.8`
- Run window: `2026-08-07T15:19:14.365157041Z` to `2026-08-07T15:19:34.495088034Z`
- Source archive SHA-256: `72ac4328fb8246fdf7e2135b1fe1051efd0115048f156f45fc9b7c4f417ac71c`
- Binary SHA-256: `4f17ef8a26c595c6c54bf4fc030c066f50baf6d0c6bc53c32b5346b99edf3a2a`
- Primary settings SHA-256: `4345cf7b58eb1794d3be3270405c0c4a6ee368b0755a3a4541f805ab3dd7bfe6`
- Native build flags: `-C target-cpu=native -C codegen-units=1 -C embed-bitcode=yes -C lto=fat -C panic=abort`

Calibration targeted `200,000 ns` and selected `72,527` loop iterations. The
retained 512-repetition mean was `200,346 ns`. This is a recorded observation,
not a tolerance gate.

## Exact mechanism checks

Every one of the 16 naive main processes completed 64 logical callers through
64 independent flights, 192 physical attempts, and 128 retries. Every one of
the 16 controlled main processes completed the same 64 logical callers through
one leader, 63 followers, one flight, three physical attempts, and two retries.
No main process shed a caller. Naive origin activity reached the cap of four;
controlled activity peaked at one. Both admitted exactly 64 callers.

The saturation control admitted 64 callers, shed 64, and made three physical
attempts in one flight. The one-token control propagated `retry_exhausted` to
all 64 admitted callers after two transient attempts, with no completion or
shedding. Independent receipt validation recomputed every count from the raw
logical and physical rows.

## Timing result

The primary complete-block estimate was:

```text
controlled / naive burst_ns = 0.132139
95% t interval              = [0.123393, 0.141505]
blocks                       = 8
SD of block log ratios       = 0.0819153
```

The descriptive process means were `1,593,547 ns` for controlled and
`12,054,215 ns` for naive. Those grand means are not the primary estimator.
The four-block controlled A/A label ratio was `0.991313`; it is a descriptive
path diagnostic, not an inferential calibration.

`burst_ns` runs from release through the end-barrier rendezvous. It includes
end-barrier release overhead and is not exactly `max(settled_ns)`. It excludes
thread joins and CSV serialization. The result applies only to this source,
binary, synthetic one-key workload, host, CPU set, and run window.

## Generated code and retained evidence

The final linked image retains `topic28_origin_work` and direct `bl` call sites.
Its loop contains `madd`, rotated `eor`, a decrement, and a conditional branch.
This establishes the measured CPU-work loop in the final image; it does not
establish coalescing, retry ownership, DNS behavior, or network behavior.

Archive:
[`raw/64ec37b/topic28-64ec37b-arm-results.tar.gz`](raw/64ec37b/topic28-64ec37b-arm-results.tar.gz)

- Bytes: `55,533,023`
- SHA-256: `730869725d4254f7a16638fa2412f4d9b79c45dc183f6313c52bb3d0909da5b7`
- Internal `evidence.sha256`: PASS
- `receipt-validation.txt`: `receipt validation: PASS`
