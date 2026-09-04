# Compact raw-evidence index

Each dated directory retains only reviewable identities and validation results.
Full sealed receipts stay outside Git under the curriculum evidence directory.
The compact files bind those receipts by SHA-256 without checking in generated
binaries, archives, assembly, disassembly, or host dumps.
