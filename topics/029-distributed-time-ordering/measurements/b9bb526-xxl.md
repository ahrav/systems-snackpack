# `xxl` exact-source result: `b9bb526`

Runtime alias `xxl` resolved to
`dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`, confirmed `x86_64`, and
completed the Topic 29 correctness, generated-code, and workspace gates from
source commit `b9bb52610705d3cd31c3d03bc532f0fb982ac175`.

## Host and source

- Requested SSH alias: `xxl`
- Resolved host: `dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com`
- Architecture: `x86_64`
- Full uname: `Linux dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com
  6.12.94-123.180.amzn2023.x86_64 #1 SMP PREEMPT_DYNAMIC Thu Jul 9 21:10:41
  UTC 2026 x86_64 x86_64 x86_64 GNU/Linux`
- CPU receipt: 192 CPUs; Intel Xeon Platinum 8488C; family `6`, model `143`,
  stepping `8`; KVM
- Toolchain: rustc `1.97.1`, LLVM `22.1.6`, Cargo `1.97.1`, GCC `11.5.0`,
  GNU objdump `2.41-50.amzn2023.0.5`
- Generic target features: `fxsr,sse,sse2`
- Native target features: `adx,aes,avx,avx2,avx512bf16,avx512bitalg,
  avx512bw,avx512cd,avx512dq,avx512f,avx512fp16,avx512ifma,avx512vbmi,
  avx512vbmi2,avx512vl,avx512vnni,avx512vpopcntdq,avxvnni,bmi1,bmi2,
  cmpxchg16b,f16c,fma,fxsr,gfni,lzcnt,movbe,pclmulqdq,popcnt,rdrand,
  rdseed,sha,sse,sse2,sse3,sse4.1,sse4.2,ssse3,vaes,vpclmulqdq,xsave,
  xsavec,xsaveopt,xsaves`
- Build controls: generic `RUSTFLAGS` unset; native
  `RUSTFLAGS=-C target-cpu=native`; workspace gates with `RUSTFLAGS` unset
- Source archive SHA-256:
  `3f2b9fce6bd030e84a7af92d1371b1fd7dcadc8a857c2a99a64591623c0b3fc1`
- Source-manifest SHA-256:
  `6f65c04cf0a1336ebecd6d20ef7969c5a528c20430d866df5f46543789e1c0a9`
- Run window: `2026-08-08T14:28:54.584414095Z` to
  `2026-08-08T14:29:02.244471171Z`

The source manifest was identical before and after the run.

## Correctness result

The generic binary SHA-256 was
`4ac8055ff5e8fd4f26e148a47077b9f73c73e4bd1ffc4f276213cf4acf8832f0`.
The native binary SHA-256 was
`c5bf8fe54cf23a2c6d769bb458c1061813a5f289e19ec08e45afa02e98100dc1`.

Each binary ran in eight fresh processes. All 16 processes exited zero, wrote
no standard error, and produced the expected receipt SHA-256
`050fe3fc9f8bb48a91be427585918e0c3b88850cfc6b3e1c8f2aaadd94d1986f`.
Independent validation recomputed every retained output and digest. Package
tests, workspace library/example tests, doctests, clippy, bench construction,
rustdoc warnings, and source stability passed.

## Generated code

The final native image retained all four requested symbols. Observed x86-64
lowering used `cmp` plus `seta` for wall selection and `cmp`, `cmova`, and `lea`
for Lamport receive. Vector comparison used conditional branches. HLC receive
used conditional moves and branches; `inc` plus `cmove` implemented the checked
logical increment and `(0,0)` overflow sentinel.

These are final-image instruction observations. They do not measure latency,
clock accuracy, networking, persistence, or a distributed protocol.

Archive:
[`raw/b9bb526/topic29-b9bb526-xxl-results.tar.gz`](raw/b9bb526/topic29-b9bb526-xxl-results.tar.gz)

- Bytes: `446,465`
- SHA-256: `090df05ea9b1ed901bcbec98605d882d4eb7c1d96ab781f8f6d4c865228f7e22`
- Internal `SHA256SUMS`: PASS
