# Retrieval and validation receipt

The following checks passed after both result archives were retrieved:

```text
arm result archive SHA-256:
d82eb35263adc4dd857bda7974ada8f8a6fb831099e7f6e4662e0b63a46dcc86

xxl result archive SHA-256:
141cc5201df8a3678d970b9a60c9770acfda8cac50a08019c9c418c1fc85ff25

source archive SHA-256:
d6390131f621c0e6d48280f6b9091cd621b831dfaad622fcd54a983b5408e4c7

Arm receipt validation:
receipt_validation=PASS processes=8 future_large_bytes=4099 future_small_bytes=16 timing_reported=no

xxl receipt validation:
receipt_validation=PASS processes=8 future_large_bytes=4099 future_small_bytes=16 timing_reported=no
```

For each extracted result directory, `shasum -a 256 -c evidence.sha256`
verified every retained file. The checked-in validator independently rechecked
all 16 raw process receipts. The canonical output files were byte-identical
across hosts.
