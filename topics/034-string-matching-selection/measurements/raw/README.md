# Raw evidence archives

Each directory is named for the measured source commit's short identifier. The
outer `SHA256SUMS` manifest verifies the retrieved host archives. Each archive
contains host metadata, source identity, generic and native correctness logs,
calibration, complete schedules, raw process rows, summaries, independent
validation, binary hashes, and linked-code inspection.

The archives support only their named source commit, hosts, binaries, inputs,
and run windows. They are not evidence for later source changes or for other
processor families.
