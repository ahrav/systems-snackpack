# Arm exact-source result: `b9bb526`

The required Arm host completed the Topic 29 correctness, generated-code, and
workspace gates from source commit
`b9bb52610705d3cd31c3d03bc532f0fb982ac175`.

## Host and source

- SSH target: `dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com`
- Architecture: `aarch64`
- Full uname: `Linux dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com
  6.12.94-123.192.amzn2023.aarch64 #1 SMP Fri Jul 24 13:35:21 UTC 2026
  aarch64 aarch64 aarch64 GNU/Linux`
- CPU receipt: 64 CPUs; DMI product `c7g.16xlarge`; implementer `0x41`,
  architecture `8`, variant `0x1`, part `0xd40`, revision `1`
- Toolchain: rustc `1.95.0`, LLVM `22.1.2`, Cargo `1.95.0`, GCC `11.5.0`,
  GNU objdump `2.41-50.amzn2023.0.5`
- Generic target features: `neon`
- Native target features: `aes,bf16,crc,dit,dotprod,dpb,dpb2,fcma,fhm,flagm,
  fp16,i8mm,jsconv,lor,lse,neon,paca,pacg,pan,pmuv3,rand,ras,rcpc,rcpc2,
  rdm,sha2,sha3,sm4,spe,ssbs,sve,vh`
- Build controls: generic `RUSTFLAGS` unset; native
  `RUSTFLAGS=-C target-cpu=native`; workspace gates with `RUSTFLAGS` unset
- Source archive SHA-256:
  `3f2b9fce6bd030e84a7af92d1371b1fd7dcadc8a857c2a99a64591623c0b3fc1`
- Source-manifest SHA-256:
  `6f65c04cf0a1336ebecd6d20ef7969c5a528c20430d866df5f46543789e1c0a9`
- Run window: `2026-08-08T14:28:56.525557282Z` to
  `2026-08-08T14:29:09.687312933Z`

The source manifest was identical before and after the run.

## Correctness result

The generic binary SHA-256 was
`327ac12e28599ee1bb0cbf94f2a6951868ed3bc6db76adc16266c0472b998ca8`.
The native binary SHA-256 was
`41ed963de607cf406ddd79df9ffacdd55944bca9694e635a76aaaf4a64c927ce`.

Each binary ran in eight fresh processes. All 16 processes exited zero, wrote
no standard error, and produced the expected receipt SHA-256
`050fe3fc9f8bb48a91be427585918e0c3b88850cfc6b3e1c8f2aaadd94d1986f`.
Independent validation recomputed every retained output and digest. Package
tests, workspace library/example tests, doctests, clippy, bench construction,
rustdoc warnings, and source stability passed.

## Generated code

The final native image retained all four requested symbols. Observed AArch64
lowering used `cmp` plus `cset` for wall selection and `cmp`, `csel`, and `add`
for Lamport receive. Vector comparison used conditional branches. HLC receive
used `csel`, `ccmp`, and checked `adds`; the overflow path selected the `(0,0)`
sentinel.

These are final-image instruction observations. They do not measure latency,
clock accuracy, networking, persistence, or a distributed protocol.

Archive:
[`raw/b9bb526/topic29-b9bb526-arm-results.tar.gz`](raw/b9bb526/topic29-b9bb526-arm-results.tar.gz)

- Bytes: `436,769`
- SHA-256: `13d694329663a0afd1bc12d7277badb8916ad70da0915d144fa4cb6dda5336df`
- Internal `SHA256SUMS`: PASS
