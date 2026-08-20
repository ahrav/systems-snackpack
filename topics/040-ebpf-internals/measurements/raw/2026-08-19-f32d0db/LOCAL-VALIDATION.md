# Retrieved-bundle validation

Both retrieved archives were extracted into private scratch directories and
validated with the checked-in semantic contract:

```text
receipt_validation=PASS ordinary_permission_processes=1 fresh_privileged_processes=8 jit_disassemblies=16 timing_reported=no
receipt_validation=PASS ordinary_permission_processes=1 fresh_privileged_processes=8 jit_disassemblies=16 timing_reported=no
```

The archive SHA-256 digests were then checked against `SHA256SUMS`.
