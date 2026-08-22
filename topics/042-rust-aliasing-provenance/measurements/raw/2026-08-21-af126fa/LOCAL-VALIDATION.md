# Local validation

The final staged artifact passed these commands on 2026-08-21. The complete
command output and summary are retained in `local-validation.tar.gz`.

```text
git diff --check
cargo fmt --all -- --check
cargo test --workspace --lib --examples
cargo test --workspace --doc
cargo clippy --workspace --all-targets -- -D warnings
cargo bench --workspace --no-run
RUSTDOCFLAGS='-D warnings' cargo doc --workspace --no-deps
cargo test --workspace --lib --bins --examples
```

After retrieval, both sealed result archives passed their internal
`bundle-manifest.sha256` files on 2026-08-21. Both also passed the validator,
which requires the expected source commit, archive digest, hostname, and
toolchain identity:

```text
python3 -I -B experiment/validate_receipts.py --root XXL_ROOT \
  --expected experiment/expected.txt \
  --source-commit af126fa920f51969667e02b926786cca598212ea \
  --archive-sha256 f83290e6f41ec6c704cd61f2033bae1f90e749dbd2799137172a7ab322e99b7d \
  --expected-hostname dev-dsk-ahrav-2c-32182091.us-west-2.amazon.com \
  --expected-rustc-version 1.93.1 \
  --expected-llvm-version 21.1.8

python3 -I -B experiment/validate_receipts.py --root ARM_ROOT \
  --expected experiment/expected.txt \
  --source-commit af126fa920f51969667e02b926786cca598212ea \
  --archive-sha256 f83290e6f41ec6c704cd61f2033bae1f90e749dbd2799137172a7ab322e99b7d \
  --expected-hostname dev-dsk-ahrav-2b-7dc7bd93.us-west-2.amazon.com \
  --expected-rustc-version 1.93.1 \
  --expected-llvm-version 21.1.8
```

Every expected value is supplied by the verifier rather than read back from the
bundle, so the validator cannot report a pass for a bundle built from different
source, produced on another host, or built with another compiler. The `xxl`
hostname above is the runtime resolution recorded in `xxl-resolution.txt`; the
Arm hostname is the fixed authorized label.

Each validator reported eight fresh processes, no timing, reference `noalias`,
one reference source load, no raw `noalias`, and two raw source loads.

The same local run rechecked `SHA256SUMS` and both retrieved host bundles with
the checked-in validator. The Linux archives remain the authority for the exact
source candidate's seven on-host workspace gates; the local archive records the
final evidence tree and post-retrieval checks.
