# Two-host comparison

Both records attest source commit `4f54c4d` and Git archive SHA-256
`23c78439fca8d965325b5182492a8449fa50795cbfe86814a9793c2e8baac9d9`.
The literal Arm target and runtime-resolved `xxl` target passed the same model,
process-crash oracle, benchmark-row validator, code-generation check, source
immutability check, and workspace gates.

| Exact host | Architecture | B/A ratio | Block log-ratio SD | Exploratory 95% interval |
| --- | --- | ---: | ---: | ---: |
| Arm literal | AArch64 | 0.128146 | 0.040686 | [0.123860, 0.132580] |
| `xxl` resolved host | x86-64 | 0.130341 | 0.056076 | [0.124372, 0.136597] |

On each host, grouping eight records reduced the declared durability calls
from 128 to 16. B used about 12.8% and 13.0% of A's elapsed I/O time in these
run windows. The similar ratios are two observations, not evidence that Arm
and x86, these CPU families, or Amazon Elastic Block Store generally behave the
same.

Generated CRC-32C code differed. The Arm binary used scalar integer
instructions. The x86 binary used a mixture of scalar and AVX/AVX-512
operations. Neither used its architecture's dedicated CRC instruction. That
code-generation difference belongs to framing and recovery CPU work; it does
not explain the barrier-dominated timing comparison.

`strace` was unavailable on both targets during the initial research run. The
retained binary's dynamic symbols expose the expected write and sync functions,
and the validator checks declared sync counts, but no syscall trace is claimed.
Neither run removed power or proved the lower storage stack's flush contract.
