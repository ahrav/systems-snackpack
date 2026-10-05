# Primary sources

Read 2026-10-05. These are source contracts, not measurement evidence.

- [subtle 2.6.1](https://docs.rs/subtle/2.6.1/subtle/): best-effort protection,
  Choice, debug/release boundary and compiler limitations.
- [ConstantTimeEq](https://docs.rs/subtle/2.6.1/subtle/trait.ConstantTimeEq.html):
  slice length short circuit and content-independent comparison intent.
- [Rust black_box](https://doc.rust-lang.org/std/hint/fn.black_box.html):
  best-effort benchmark control, no cryptographic security guarantee.
- [BearSSL constant-time](https://bearssl.org/constanttime.html): branch,
  address and operand-timing models; compiler transformations.
- [libsodium helpers](https://doc.libsodium.org/helpers): sodium_memcmp equality
  contract and distinction from lexicographic comparison.
- [dudect](https://github.com/oreparaz/dudect): leakage detection, exact-platform
  dependence, and why failure to detect is not proof.
- [Verifying Constant-Time Implementations, USENIX Security 2016](https://www.usenix.org/conference/usenixsecurity16/technical-sessions/presentation/almeida):
  relational security model and verification scope.
