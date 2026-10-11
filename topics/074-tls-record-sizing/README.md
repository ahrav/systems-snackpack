# TLS record sizing

Compare local send caps while preserving application write boundaries. The Rust
library budgets TLS 1.3 content, inner type, padding, and fixed 16-byte tags with
checked arithmetic. It is not encryption. The C fixture uses OpenSSL 3.x memory
BIOs for actual TLS 1.3 AES-128-GCM encryption and decryption.

```bash
cargo test -p tls-record-sizing
cargo run -p tls-record-sizing --example budget
cd topics/074-tls-record-sizing
cc -std=c11 -O3 -Wall -Wextra -Werror probe.c $(pkg-config --cflags --libs openssl) -o /tmp/topic074-probe
/tmp/topic074-probe 16384 65536 65536 64
python3 check.py /tmp/topic074-probe
python3 -m unittest test_gates
python3 run.py /tmp/topic074-new-results
python3 analyze.py /tmp/topic074-new-results
```

Use a new output directory. `test_gates.py` runs each script against fake probes
with and without `PYTHONOPTIMIZE` and requires explicit rejection of incorrect
rows, accepted invalid inputs, partial candidate sets, missing blocks, runtime
library mismatches, and source changes during a campaign. Requirements: Python 3, C compiler, `pkg-config`,
OpenSSL 3.x headers/libraries, and the workspace Rust toolchain. The fixture
creates and trusts an ephemeral certificate in memory, verifies its hostname,
and never opens a network listener. It is not a production TLS wrapper.

`probe CAP LENGTH WRITE_SIZE REPEATS` accepts the three tested caps (1024,
4096, 16384), positive lengths/write sizes up to 1 MiB, and up to one million
repeats. It checks decrypted bytes, framing lengths, record count, and wire bytes.
Truncated and corrupted records must release no plaintext. A withheld final byte
must allow the intact record to complete when delivered.

A negotiated peer receive bound includes the inner type and padding; a local
OpenSSL send cap has a different API contract. A cap does not coalesce already
flushed writes. A TLS record can cross TCP segments. QUIC has separate packet
protection. See [sources](references.md), [measurement contract](measurements.md),
and [round notes](rounds/01.md).
