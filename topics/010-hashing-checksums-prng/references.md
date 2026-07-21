# References

- [Rust `HashMap`](https://doc.rust-lang.org/std/collections/struct.HashMap.html) — Default keyed hashing contract and resistance to algorithmic-complexity attacks.
- [Rust `Hash`](https://doc.rust-lang.org/std/hash/trait.Hash.html) and [`Hasher`](https://doc.rust-lang.org/std/hash/trait.Hasher.html) — Language contracts and portability limits for hash input and output.
- [SipHash](https://www.aumasson.jp/siphash/siphash.pdf) — A keyed PRF designed for short-input hash-table use.
- [xxHash specification](https://github.com/Cyan4973/xxHash/blob/dev/doc/xxhash_spec.md) — Stable byte-level specifications for the xxHash family.
- [CRC RevEng: CRC-32/ISCSI](https://reveng.sourceforge.io/crc-catalogue/17plus.htm#crc.cat.crc-32-iscsi) — CRC-32C parameters and standard check value.
- [CRC RevEng: CRC-32/ISO-HDLC](https://reveng.sourceforge.io/crc-catalogue/17plus.htm#crc.cat.crc-32-iso-hdlc) — Ethernet/ZIP CRC parameters and check value.
- [Intel SSE4.2 CRC32 instruction](https://www.intel.com/content/www/us/en/docs/intrinsics-guide/index.html#text=_mm_crc32_u64) — x86 CRC32C instruction semantics and feature boundary.
- [Arm ACLE CRC intrinsics](https://arm-software.github.io/acle/main/acle.html#crc32-intrinsics) — Arm CRC32 and CRC32C intrinsic contracts.
- [zlib `crc32_combine`](https://zlib.net/manual.html#Checksum) — Composition of CRCs for concatenated streams.
- [Blackman and Vigna, *Scrambled Linear Pseudorandom Number Generators*](https://vigna.di.unimi.it/ftp/papers/ScrambledLinear.pdf) — xoshiro-family structure, state transitions, and output scramblers.
- [xoshiro reference implementations](https://prng.di.unimi.it/) — Named algorithms, jump functions, and reference code.
- [Salmon et al., *Parallel Random Numbers: As Easy as 1, 2, 3*](https://www.thesalmons.org/john/random123/papers/random123sc11.pdf) — Counter-based random generation and independent stream construction.
- [Rust Rand reproducibility guide](https://rust-random.github.io/book/guide-reproducibility.html) — Algorithm, version, seed, and consumption-order boundaries.
- [Lemire, *Fast Random Integer Generation in an Interval*](https://arxiv.org/abs/1805.10941) — Multiply-high bounded sampling with rejection and bias analysis.
- [Kalibera and Jones, ISMM 2013](https://doi.org/10.1145/2464157.2464160) — Process-level replication and benchmark uncertainty.
