# Cross-host comparison: `bf93921`

Both exact-source runs support the same narrow conclusion: in this bounded
single-worker system, the prescribed variable service shape increased queue
wait and rejection and reduced goodput despite matched offered mean loop work.

| Block-level outcome | Arm | `xxl` |
| --- | ---: | ---: |
| Mean-wait difference | `507,562 ns` `[501,232, 513,893]` | `499,834 ns` `[495,171, 504,498]` |
| p50-wait difference | `98,931 ns` `[63,565, 134,296]` | `26,315 ns` `[20,094, 32,536]` |
| p99-wait difference | `2,153,967 ns` `[1,916,320, 2,391,614]` | `2,139,827 ns` `[1,907,041, 2,372,613]` |
| Rejection difference | `21.6664 pp` `[21.3168, 22.0160]` | `22.6492 pp` `[22.4013, 22.8972]` |
| Variable/fixed goodput | `0.782825` `[0.779324, 0.786341]` | `0.773017` `[0.770494, 0.775548]` |

`pp` means percentage points. Each interval covers variation among eight
complete four-process block contrasts in one run window. It does not cover
request-to-request samples, independent days, other hosts, production traffic,
or source changes. Sequential host state can persist across blocks, so the
Student-t interval is a model-based summary rather than a universal confidence
guarantee.

The fixed and variable treatments offered the same number of loop iterations
per ten requests. The variable treatment placed one `7.75x` job among nine
`0.25x` jobs. The observed final binaries retained the loop on both hosts, and
the generator-lateness treatment intervals included zero. These controls make
worker blocking and queue filling the supported mechanism in this experiment.
They do not identify an instruction-set, vendor, or processor-family effect.

The first exact commit, `388531c`, passed the focused source gates on both
hosts but failed before measurement because fat link-time optimization lacked
embedded bitcode. Its failure bundles were sealed and source-stable but are not
promoted here. Commit `bf93921` added `-C embed-bitcode=yes`; each host then
reran 48 fresh processes from the beginning, 96 processes across both hosts,
with no period replacement.

See the [Arm record](bf93921-arm.md), [`xxl` record](bf93921-xxl.md), and
[raw archive checksums](raw/bf93921/SHA256SUMS).
