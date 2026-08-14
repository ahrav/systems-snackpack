# Raw evidence archives

Each directory is named for the measured source commit's short identifier. The
outer `SHA256SUMS` file verifies the retrieved host archives. Each archive
contains host metadata, source identity, build and correctness logs,
calibration, process schedules, raw rows, summaries, independent validation,
binary hashes, and linked-code inspection.

The archives support only their named source commit, hosts, binaries, inputs,
and run windows. They do not support later source changes or processor-family
claims.
