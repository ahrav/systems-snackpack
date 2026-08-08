# Raw evidence

Each source-prefix directory retains one immutable archive from the required
Arm host and one from the runtime-resolved `xxl` host. A promoted archive
contains exact source identity, host and toolchain receipts, workspace gates,
the final binary and code-generation evidence, the fixed process schedule, raw
logical and physical receipts, analysis, independent validation, final status,
and an internal `evidence.sha256` manifest.

`SHA256SUMS` binds the two outer archives. Verify both the outer digest and the
internal manifest after extracting into a new empty directory. Never overwrite
a failed or superseded bundle; a new run or source correction receives a new
identity.

## `64ec37b` archives

| Archive | Bytes | SHA-256 |
| --- | ---: | --- |
| `topic28-64ec37b-arm-results.tar.gz` | `55,533,023` | `730869725d4254f7a16638fa2412f4d9b79c45dc183f6313c52bb3d0909da5b7` |
| `topic28-64ec37b-xxl-results.tar.gz` | `55,668,260` | `a1b4787e4d3c733a15e18e3c800437631858fffe30363e955b5248d97df32c68` |

Verify one archive after extraction:

```bash
cd topics/028-backpressure-overload/measurements/raw/64ec37b
sha256sum --check SHA256SUMS
mkdir /tmp/topic28-arm-64ec37b
tar -xzf topic28-64ec37b-arm-results.tar.gz -C /tmp/topic28-arm-64ec37b
cd /tmp/topic28-arm-64ec37b/results
sha256sum --check evidence.sha256
```

Use a new empty directory. Substitute the `xxl` archive and directory for the
second host.
