# `xxl` exact-source result: `64ec37b`

Runtime alias `xxl` resolved to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com` and completed the full Topic 28
protocol from source commit `64ec37b944051279f71c3af32de050b94f7d824e`.
All workspace, source-stability, code-generation, schedule, semantic-control,
raw-receipt, analysis, and evidence manifest gates passed.

## Host and artifact

- Requested alias: `xxl`
- Resolved host: `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`
- Architecture and CPU: `x86_64`, Intel Xeon Platinum 8488C under KVM
- Kernel: `6.12.94-123.180.amzn2023.x86_64`
- CPUs: 192 available; every calibration and treatment process used CPUs `0,1,2,3`
- Clock source: `tsc`
- Toolchain used after the controlled environment sweep: rustc/Cargo `1.93.1`, LLVM `21.1.8`
- Run window: `2026-08-07T15:19:14.218385998Z` to `2026-08-07T15:19:29.387137746Z`
- Source archive SHA-256: `72ac4328fb8246fdf7e2135b1fe1051efd0115048f156f45fc9b7c4f417ac71c`
- Binary SHA-256: `40b3e0182ecab1c39ffe55b4f856a476ef416aeed33b328e4c5b6274c1c25b68`
- Primary settings SHA-256: `ccdb4b0589ca5a3446cf57767cbe54471b6fbe1b8e71fe70878b3d442ee9702f`
- Native build flags: `-C target-cpu=native -C codegen-units=1 -C embed-bitcode=yes -C lto=fat -C panic=abort`

Calibration targeted `200,000 ns` and selected `105,878` loop iterations. The
retained 512-repetition mean was `199,080 ns`. This is a recorded observation,
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
controlled / naive burst_ns = 0.123703
95% t interval              = [0.108537, 0.140989]
blocks                       = 8
SD of block log ratios       = 0.156449
```

The descriptive process means were `1,613,312 ns` for controlled and
`13,085,532 ns` for naive. Those grand means are not the primary estimator.
The four-block controlled A/A label ratio was `0.991541`; it is a descriptive
path diagnostic, not an inferential calibration.

`burst_ns` runs from release through the end-barrier rendezvous. It includes
end-barrier release overhead and is not exactly `max(settled_ns)`. It excludes
thread joins and CSV serialization. The result applies only to this source,
binary, synthetic one-key workload, host, CPU set, and run window.

## Generated code and retained evidence

The final linked image retains `topic28_origin_work` and direct `call` sites.
Its loop contains `imul`, `add`, `rorx`, `xor`, a decrement, and a conditional
branch. This establishes the measured CPU-work loop in the final image; it does
not establish coalescing, retry ownership, DNS behavior, or network behavior.

Archive:
[`raw/64ec37b/topic28-64ec37b-xxl-results.tar.gz`](raw/64ec37b/topic28-64ec37b-xxl-results.tar.gz)

- Bytes: `55,668,260`
- SHA-256: `a1b4787e4d3c733a15e18e3c800437631858fffe30363e955b5248d97df32c68`
- Internal `evidence.sha256`: PASS
- `receipt-validation.txt`: `receipt validation: PASS`
