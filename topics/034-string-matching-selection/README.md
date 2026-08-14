# String matching algorithm selection

Exact substring search asks for the first byte position where a needle occurs in
a haystack. The hard part is not implementing one matcher. It is choosing a
matcher whose setup work, progress rule, and failure mode fit the workload.
Short one-shot searches and long reused searches need different tradeoffs, and
repetitive data can reverse a result observed on random bytes.

This crate defines three exact byte matchers with one shared contract:

- an empty needle returns `Some(0)`;
- a longer needle cannot match a shorter haystack;
- every byte value is data; and
- a match is the first byte offset, including overlaps.

Byte offsets do not imply character boundaries or Unicode equivalence. Search
encoded text only when exact equality of its encoded bytes is the required
contract.

The crate is a teaching probe, not a replacement for a maintained standard
library or the [`memchr`](https://docs.rs/memchr/latest/memchr/memmem/) crate.
It omits vector dispatch, Crochemore-Perrin Two-Way search, full Boyer-Moore,
Rabin-Karp hashing, multi-pattern search, Unicode normalization, and production
API tuning.

## Three progress rules

The left-to-right matcher tests each possible start in order. It first checks
the needle's first byte, then compares the complete candidate window. It has no
preparation cost. A haystack full of `a` searched for `aaaa...ab` makes it
repeat almost the whole comparison at every alignment, so its worst-case work
is proportional to the haystack length times the needle length.

Knuth-Morris-Pratt (KMP) prepares a prefix table. On a mismatch, the table says
which prefix of the needle is still useful, so the search never backs up in the
haystack. Construction uses time and storage proportional to the needle length.
The complete prepare-and-search operation is linear in the combined input
length. KMP fits streaming or hostile repetitive input when bounded work
matters. Its allocation, table accesses, and dependent fallback steps remain
part of the elapsed cost.

Boyer-Moore-Horspool prepares one shift for each possible byte. It compares a
window from right to left, then uses the aligned window's final byte to advance
past starts that cannot match. Favorable, longer, reused needles can skip many
candidate starts. A haystack full of `a` searched for `baaa...a` forces a
near-complete backward comparison and a one-byte shift at every alignment, so
Horspool also has a multiplicative worst case.

| Method | Problem it solves | What it does not solve | Main catch | Choose it when |
| --- | --- | --- | --- | --- |
| Left-to-right | Avoids setup and rejects a mismatching first byte cheaply | Repeated prefixes | Repeats long forward comparisons | The search is small or one-shot and the first byte is selective |
| KMP | Guarantees forward progress without backing up in the haystack | Setup cost or peak vector throughput | Prefix-table construction and dependent fallback steps | Input is streamed or adversarial linear work matters |
| Horspool | Skips multiple candidate starts on favorable data | Low-entropy or hostile suffixes | Quadratic worst case and a 256-entry table | A longer needle is reused and representative data proves useful shifts |

Production matchers often combine techniques. For example, `memchr` 2.8.3
uses special handling for empty and one-byte needles, low-startup Rabin-Karp on
tiny inputs, packed two-byte candidate filters for short needles, and a
deterministic Two-Way fallback for longer searches. These cutoffs are
version-specific implementation choices, not universal constants.

## Cost model

First ask where the work comes from. For a haystack of `n` bytes, a needle of
`m` bytes, and `R` searches that reuse one prepared needle, approximate one
search as:

```text
time ~= P(m) / R + scan_work + q * (n - m + 1) * verification_work
```

`P(m)` is needle-preparation cost. `q` is the fraction of possible starts that
survive the cheap filter. The last term grows when a common anchor byte or a
periodic suffix admits many candidates. A vector filter that checks `W` byte
positions at once changes the scan term to roughly:

```text
scan_work ~= ceil((n - m + 1) / W) * cost_per_vector
```

These are analytical models, not processor simulators. They support concrete
decisions: reuse reduces preparation cost per query, a rare anchor lowers `q`,
and repetitive input raises verification work. Cache behavior, branch
prediction, compiler output, and scheduling remain host-specific.

## Run the focused experiment

From the repository root:

```bash
cargo test --locked --package string-matching-selection

cargo run --locked --release \
  --package string-matching-selection \
  --bin string-match-probe -- verify

RUSTFLAGS="-C target-cpu=native -C debuginfo=1" \
  cargo build --locked --release \
  --package string-matching-selection \
  --bin string-match-probe

python3 -I topics/034-string-matching-selection/experiment/run_processes.py \
  --binary target/release/string-match-probe \
  --output /tmp/topic034-results \
  --blocks 12 \
  --aa-blocks 4 \
  --seed 340034 \
  --target-ms 200

python3 -I topics/034-string-matching-selection/experiment/validate_receipts.py \
  /tmp/topic034-results
```

The output directory must not exist. The runner first freezes a repetition map,
then launches one method per fresh process. It keeps five cases separate:

- uniform-looking bytes with an absent 32-byte needle;
- skewed text with a late 16-byte match;
- a repeated-prefix trap for left-to-right comparison;
- a repeated-suffix trap for Horspool; and
- a small haystack with a late four-byte match.

Each process reports both `reuse`, where plan construction is outside the timed
interval, and `one_shot`, where construction and one search are timed together.
Corpus construction, oracle validation, calibration, output, and process
startup are outside the steady-state interval.

The runner compares left-to-right against KMP and against Horspool in separate
12-block families. Each four-period block uses an `ABBA` or `BAAB` order, where
`A` is the baseline and `B` is the candidate. The schedule therefore launches
112 timed processes and retains 1,120 case-and-mode rows. The reported ratio is
the geometric mean of 12 complete-block log contrasts. Its sample standard
deviation covers block-to-block variation in that exact run window. Inner-loop
searches are repeated subsamples, not independent runs. Four left-to-right
against itself blocks check the schedule and analysis path; they do not define
a universal noise floor.

The source code predicts bounded forward progress for KMP on both periodic
traps, repeated forward near-matches for left-to-right on the prefix trap, and
repeated backward near-matches for Horspool on the suffix trap. These mechanism
predictions are not timing pass criteria. Preparation enters every timed
iteration in `one_shot` mode and stays outside the interval in `reuse` mode.
The elapsed-time winner can differ by case, host, compiler, and generated
instructions.

See [`rounds/01.md`](rounds/01.md) for the acceptance contract,
[`measurements/README.md`](measurements/README.md) for the evidence boundary,
and [`references.md`](references.md) for primary sources and version limits.

The retained exact-source result for commit `b8d7f88` passed on both required
Linux hosts. Horspool's candidate-to-left-to-right ratio ranged from 0.318 on a
favorable uniform-looking case to 50.269 on its opposing periodic trap. KMP led
only on the repeated-prefix trap. See the
[`b8d7f88` comparison](measurements/b8d7f88-comparison.md) for complete ratios,
dispersion, host boundaries, generated code, and raw evidence.
