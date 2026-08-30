# Measurement records

This directory holds compact, reviewable records from exact-source runs on the two required Linux hosts.

The checked-in summary must name the pushed commit, archive digest, resolved hostname, architecture, kernel, compiler and flags, CPU availability, filesystem and mount options, backing-device queue settings, memory, dirty-page settings, run count, complete-block estimate, interval, startup distribution, semantic controls, and code-generation observations. Each performance statement must distinguish measured elapsed time from an inferred kernel or device mechanism.

Raw sealed receipts are retained outside Git. A checked-in record must include the receipt archive path or durable location, its SHA-256 digest, its uncompressed manifest digest, and the exact validation command. Do not check in the full per-process receipt tree.

The preliminary exploration is not final evidence. Only receipts produced by the exact pushed source with [`../experiment/run_host.sh`](../experiment/run_host.sh) qualify for the checked-in measurement record.

See [`raw/README.md`](raw/README.md) for the required raw receipt layout and cleanup boundary.
