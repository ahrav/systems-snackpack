# Exact-source host comparison

Both required hosts built the same archived source and passed the same
correctness oracles.

| Check | Arm | `xxl` |
|---|---|---|
| source commit | `e8f5f459` | `e8f5f459` |
| archive and runner identity | pass | pass |
| source inventory before and after | identical | identical |
| baseline setup | SQ 8, CQ 16 | SQ 8, CQ 16 |
| wrong `SINGLE_ISSUER` task | `-EEXIST` | `-EEXIST` |
| deferred CQEs before owner `GETEVENTS` | 0 | 0 |
| deferred timeout terminal result | `-ETIME` | `-ETIME` |
| async-cancel request result | 0 | 0 |
| target terminal result | `-ECANCELED` | `-ECANCELED` |
| process A/A control | identical | identical |
| independent sealed validation | 17 entries | 17 entries |

The matching observations show that these four contracts behaved alike in the
two run windows. They do not establish an instruction-set, processor-vendor,
or performance property.

The hosts differ in processor topology, kernel build, virtualization, and
Rust toolchain. No elapsed-time comparison was collected or inferred. The
probe does not exercise storage or the excluded `io_uring` modes and resource
classes listed in each host record.
