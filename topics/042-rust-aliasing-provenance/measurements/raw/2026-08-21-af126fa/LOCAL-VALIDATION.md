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
`bundle-manifest.sha256` files on 2026-08-21. Both also passed:

```text
python3 -I -B experiment/validate_receipts.py --root HOST_ROOT \
  --expected experiment/expected.txt
```

Each validator reported eight fresh processes, no timing, reference `noalias`,
one reference source load, no raw `noalias`, and two raw source loads.

The same local run rechecked `SHA256SUMS` and both retrieved host bundles with
the checked-in validator. The Linux archives remain the authority for the exact
source candidate's seven on-host workspace gates; the local archive records the
final evidence tree and post-retrieval checks.
