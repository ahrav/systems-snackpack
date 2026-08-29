# Cross-host boundary

Both accepted campaigns used source commit
`97572e93a6ee98e14bece7501068d5cedd962571`, source-archive SHA-256
`546dd1fa3cd205fd19bc937198281e0b7b6ca929a85d657c18f68d8312c4d035`,
the same fixed inputs, and the same block schedule. Each host compiled its own
native binary with GNU Compiler Collection (GCC) 11.5.0.

| Exact-host estimate | Required AArch64 host | Runtime-resolved `xxl` host |
|---|---:|---:|
| Median A holder wall time | 192.206376 ms | 192.205819 ms |
| Median B holder wall time | 5.020124 ms | 5.009945 ms |
| Holder-wall A/B ratio | 39.092720 | 38.855392 |
| 95% between-block interval | [38.567194, 39.625406] | [38.233483, 39.487418] |
| Waiter-lock A/B ratio | 40.101059 | 40.144134 |
| 95% between-block interval | [39.716012, 40.489840] | [39.715955, 40.576930] |
| A/A holder X/Y ratio | 0.999398 | 1.000087 |
| A/A waiter X/Y ratio | 0.995586 | 1.000100 |

On both exact hosts, treatment A stretched about 5 milliseconds of holder CPU
work to about 192 milliseconds of holder wall time, while treatment B remained
near 5 milliseconds. All four A/A intervals included one. These are two separate
host observations, not a pooled estimate.

The Arm host environment exposed one logical thread per core and no SMT
control. The x86 guest exposed two logical threads per core, but neither
treatment used the holder's sibling CPU 96. The experiment therefore does not
measure an SMT packing effect. It also does not support an Arm-versus-x86
performance claim.

Both linked binaries retained the same source-level loop boundary but used
their architecture's ordinary integer instructions. That observation confirms
that the intended timed work survived compilation. It does not make instruction
throughput or code-generation quality the cause of the timing ratio.

The 95% intervals cover variation among eight complete four-process blocks on
one exact host and run window. They do not cover machine, kernel, build,
processor-family, cloud-host, or application populations. Similar point
estimates on these two hosts do not expand that boundary.
