# Raw evidence

Store one immutable bundle below `<source-prefix>/<host-label>/` for each exact
candidate and host. A complete bundle contains:

- `host.txt` with requested and resolved targets, CPU, kernel, toolchain,
  affinity, interface, driver, queues, steering, socket, backlog, NAPI,
  busy-poll, and loopback state;
- `source-identity.txt`, `source.tar.gz`, its SHA-256, and sorted
  `source-files.before.sha256` and `source-files.after.sha256` manifests;
- `build-flags.txt`, final binary SHA-256, Executable and Linkable Format (ELF)
  headers, symbols, linked-image disassembly excerpts, and compressed full
  code-generation evidence;
- workspace validation logs and a control-smoke observation;
- `experiment/design.json`, append-only attempted and accepted process rows,
  block contrasts, UDP GRO controls, analysis summary, and run status;
- receipt-validator output, a final `run.status`, and `evidence.sha256` covering
  every retained file except the evidence manifest itself.

The final status must report source verification, build, workspace gates,
fixed schedule, affinity, call counts, datagram counts, full payload
verification, checksum, UDP GRO controls, analysis, code-generation inspection,
and hashing. Exit zero by itself is not a successful measurement.

Never overwrite a failed, partial, or superseded bundle. Retain it under its
own source prefix or attempt label and record why it was not promoted. Generate
the final evidence manifest only after all files stop changing, then rerun the
validator against the sealed bundle.
