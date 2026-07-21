# Topic 10: Hashing, checksums, and PRNG selection

Hash functions, checksums, and pseudo-random generators all mix bits. They do
not offer the same contract. Select the contract first, then measure a concrete
implementation on the deployed target.

## Selection boundary

| Requirement | Starting point | Invalid substitution |
| --- | --- | --- |
| Adversarial hash-table keys | A keyed, denial-of-service-resistant hash | A fast unkeyed hash |
| Stable file or protocol identity | A specified, versioned hash and byte encoding | A language's default table hash |
| Accidental corruption detection | The protocol's exact checksum or CRC parameters | A similarly named CRC polynomial |
| Adversarial integrity | A cryptographic MAC or authenticated-encryption tag | CRC, `Hash`, or a seeded non-cryptographic hash |
| Simulation or sampling | A named PRNG with explicit state and stream policy | A generator chosen only from one scalar benchmark |
| Secrets, nonces, or keys | An operating-system CSPRNG or a reviewed CSPRNG design | A small-state statistical PRNG |

A complete choice names semantics, input distribution, state and seeding,
deployment ISA, message-size distribution, and failure consequence. Throughput
alone answers none of those questions.

## CRC contract

This crate fixes the measured contract to reflected CRC-32C/Castagnoli:

```text
width=32 poly=0x1EDC6F41 refin=true refout=true
init=0xFFFFFFFF xorout=0xFFFFFFFF check("123456789")=0xE3069283
```

The reflected recurrence uses polynomial `0x82F63B78`. The API keeps internal
state separate from the final XOR so fragmented and contiguous updates agree.
It includes three exact implementations:

- a bit-at-a-time oracle whose control flow is independent of the table and
  hardware implementations;
- a portable 256-entry, slice-by-one table update;
- a runtime-dispatched hardware update using x86 SSE4.2 CRC instructions or
  Arm CRC32 instructions when available.

CRC-32/ISO-HDLC uses reflected polynomial `0xEDB88320` and produces
`0xCBF43926` for the same check string. That different answer is a contract
check, not an implementation defect.

## Cost model

For a message of `n` bytes, end-to-end cost is approximately:

```text
T(n) = dispatch + setup + n / steady_state_rate + tail + finalization
```

The portable loop performs a dependent table lookup per byte. The hardware
loop processes eight-byte words but retains a dependency chain through the CRC
state. Runtime feature detection should happen outside the hot loop. Small
messages can therefore be dispatch- or latency-bound even when a long-buffer
throughput result is high.

The focused benchmark does not claim peak CRC throughput. It compares a simple
table implementation with one dependent hardware instruction chain over the
same repeatedly warmed 4 KiB slice. Wider folding implementations can use carry-less
multiplication and parallel accumulators to expose more instruction-level
parallelism. They are a different implementation class.

## Failure boundaries

- The CRC name is insufficient. Record width, polynomial, reflection, initial
  value, final XOR, and check vector.
- CRC detects accidental corruption under a stated error model. It does not
  authenticate data against an attacker.
- Rust's `Hash` and `Hasher` traits do not promise stable cross-version output.
- A seed is not a cryptographic key. Reproducible PRNG streams require a named
  algorithm, version, seed mapping, stream split, and consumption order.
- Modulo reduction biases bounded random integers unless the source range is an
  exact multiple of the bound. Rejection or multiply-high methods need an
  explicitly verified bias contract.
- A hardware instruction mnemonic does not identify the surrounding algorithm.
  Inspect the linked benchmark binary built with the deployment flags.
- Inner-loop iterations are throughput work, not independent samples. Fresh
  processes are the replication unit in the recorded experiment.

## Recorded result

The final exact-source measurements are recorded under
[`measurements/`](measurements/README.md). Both hosts verify the standard check
vector, fragmented-update equivalence, offset and length boundaries, and
portable/hardware parity before timing. Timing uses 12 fresh order-balanced
process pairs per host, pinned to CPU 0. Each process hashes 1 GiB after a
64 MiB warmup. Dataset creation, dispatch selection, and warmup are outside the
steady-state timer.

The host records report elapsed time, process dispersion, exact source and
binary hashes, native compiler features, and linked-binary instructions. They
do not turn two machines into samples of an ISA, vendor, kernel, or cloud
instance family.

Candidate `2ef0239` used 12 order-balanced pairs per host. The simple
hardware chain's median speedup over the slice-by-one table was `54.830x` on
the Arm host (`dev-dsk-ahrav-2b`, `aarch64`) and `21.886x` on the x86-64 host
(`xlg`, `x86_64`); each host record links its captured `host-env.txt`. Those
ratios apply only to the exact
4 KiB, warmed-input implementation pair. They do not estimate a folding CRC,
hash function, other polynomial, or end-to-end storage path.

## Run

Check correctness:

```bash
cargo run -p systems-snackpack-topic-010 --example check_equivalence
cargo bench -p systems-snackpack-topic-010 --bench crc32c -- --verify
```

Run the Linux evidence harness from the repository root:

```bash
git archive --format=tar HEAD Cargo.toml Cargo.lock \
  topics/010-hashing-checksums-prng | gzip -9 \
  > /tmp/systems-snackpack-topic-010-source.tar.gz
topic10_source_sha=$(sha256sum \
  /tmp/systems-snackpack-topic-010-source.tar.gz | cut -d ' ' -f 1)
topics/010-hashing-checksums-prng/experiment/run_processes.sh \
  /tmp/systems-snackpack-topic-010 local "$(git rev-parse HEAD)" \
  "$topic10_source_sha"
cat /tmp/systems-snackpack-topic-010/summary.txt
```

On a remote host without the Git checkout, extract the transferred tarball and
run the harness from the extracted tree with `SOURCE_ARCHIVE` pointing at the
tarball. The harness re-hashes the tarball against `SOURCE_ARCHIVE_SHA256` and
rejects an extracted tree that differs from the archive contents.

Read [Round 1](rounds/01.md), the [measurement boundary](measurements/README.md),
and the [primary sources](references.md) before interpreting a host result.
