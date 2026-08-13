# Primary sources and version boundaries

The algorithm papers define correctness and work bounds. Current implementation
links document concrete dispatch choices as observed on 2026-08-13. Numeric
thresholds in production source are version-specific and are not API promises.

## Algorithms

- [Knuth, Morris, and Pratt, "Fast Pattern Matching in Strings"](https://doi.org/10.1137/0206024)
  derives linear search without backing up in the text and a prefix-derived
  failure function.
- [Boyer and Moore, "A Fast String Searching Algorithm"](https://www.cs.utexas.edu/~moore/publications/fstrpos.pdf)
  introduces right-to-left comparison with bad-character and good-suffix
  shifts. Its claims do not automatically apply to simplified variants.
- [Horspool, "Practical Fast Searching in Strings"](https://webhome.cs.uvic.ca/~nigelh/Publications/stringsearch.pdf)
  defines the single-shift-table variant modeled by this crate and discusses
  practical skip behavior.
- [Crochemore and Perrin, "Two-Way String-Matching"](https://www-igm.univ-mlv.fr/~mac/Articles-PDF/CP-1991-jacm.pdf)
  derives constant-word preprocessing state and a deterministic linear search
  bound from a critical factorization and the needle's period.
- [Karp and Rabin, "Efficient Randomized Pattern-Matching Algorithms"](https://doi.org/10.1147/rd.312.0249)
  analyzes rolling fingerprints. An exact implementation must verify hash
  candidates before reporting a match.
- [Aho and Corasick, "Efficient String Matching"](https://doi.org/10.1145/360825.360855)
  defines a finite-state machine for matching many patterns in one text pass.

## Current implementations and platform contracts

- [`memchr` 2.8.3 `memmem` documentation](https://docs.rs/memchr/latest/memchr/memmem/)
  states arbitrary-byte semantics, the public worst-case bound, reusable
  `Finder` behavior, and architecture support.
- [`memchr` 2.8.3 searcher source](https://docs.rs/memchr/latest/src/memchr/memmem/searcher.rs.html)
  shows the current Rabin-Karp, one-byte, packed-pair, and Two-Way selection.
- [glibc `memmem.c`](https://codebrowser.dev/glibc/glibc/string/memmem.c.html)
  shows generic GNU C Library handling for lengths zero, one, and two; a
  bounded hashed-pair Horspool region; and a Two-Way fallback.
- [Rust stable `core::str::pattern` source](https://doc.rust-lang.org/stable/src/core/str/pattern.rs.html)
  shows the standard string searcher's current internal Two-Way mechanics.
  This internal implementation is not a stable selection contract.
- [Rust `Instant`](https://doc.rust-lang.org/std/time/struct.Instant.html)
  defines the monotonic elapsed-time source used by the probe and its platform
  limits.
- [Rust `black_box`](https://doc.rust-lang.org/std/hint/fn.black_box.html)
  defines the best-effort optimization barrier. It does not replace linked-code
  inspection.
- [Unicode Standard Annex #15](https://www.unicode.org/reports/tr15/)
  defines Unicode normalization forms. Exact byte equality alone does not
  implement canonical text equivalence.

## Model boundary

The preparation, candidate-rate, vector-scan, and amortization equations in
this topic are explicit analytical models. No cited library exposes them as a
runtime cost estimator. The crate implements only the three source-defined
teaching matchers named in its README.
