# Expected observations

`wal-crash-probe model` prints `MODEL,status=pass` and its explicit scope.
`process-crash` prints three passing cut-point lines followed by a scope that
states `power_loss=false`.

For the focused benchmark, each CSV must contain 32 fresh-process rows: eight
complete blocks, four ABBA and four BAAB. Treatment A must declare 128
`fdatasync` calls; treatment B must declare 16. Both write 128 records with
256-byte payloads and a 37,888-byte log. B is expected to have a lower elapsed
I/O time on storage where durability barriers dominate this small workload,
but that direction is an expectation, not a correctness condition.
