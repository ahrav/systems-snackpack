//! Controlled kernels for three representations of one 16-bit integer chunk.
//!
//! The crate compares a sorted array, a fixed 65,536-bit bitmap, and sorted
//! inclusive runs. It isolates container-level intersection cardinality; it
//! does not implement a Roaring directory, serialization, mutation policy, or
//! production validation.
//!
//! ```
//! use roaring_bitmaps_compressed_sets::{bitmap_contains, bitmap_from_values, split_u32_id};
//!
//! let (high, low) = split_u32_id(0x1234_abcd);
//! let bitmap = bitmap_from_values(&[low]);
//! assert_eq!((high, low), (0x1234, 0xabcd));
//! assert!(bitmap_contains(&bitmap, 0xabcd));
//! assert!(!bitmap_contains(&bitmap, 0xabce));
//! ```

/// Number of possible low values in one 16-bit chunk.
pub const CONTAINER_BITS: usize = 1 << 16;

/// Number of 64-bit words in one fixed bitmap container.
pub const BITMAP_WORDS: usize = CONTAINER_BITS / u64::BITS as usize;

/// Names of the deterministic cases used by the correctness and timing probes.
pub const CASE_NAMES: [&str; 5] = [
    "tiny16",
    "sparse256",
    "threshold4096",
    "dense32768",
    "runs64",
];

/// A fixed bitmap for all 65,536 values in one 16-bit chunk.
pub type Bitmap = [u64; BITMAP_WORDS];

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(C)]
/// One non-empty inclusive interval inside a 16-bit chunk.
///
/// A valid sequence of runs is sorted by `start`, contains no overlap, and
/// contains no adjacent pair that could be merged into one run.
pub struct Run {
    /// First value included in the interval.
    start: u16,
    /// Last value included in the interval.
    end: u16,
}

impl Run {
    #[must_use]
    /// Returns a non-empty inclusive run, or `None` when `start` exceeds `end`.
    pub const fn new(start: u16, end: u16) -> Option<Self> {
        if start <= end {
            Some(Self { start, end })
        } else {
            None
        }
    }

    #[must_use]
    /// Returns the run cardinality without overflowing at `u16::MAX`.
    pub const fn cardinality(self) -> u32 {
        self.end as u32 - self.start as u32 + 1
    }

    #[must_use]
    /// Returns the first value included in the interval.
    pub const fn start(self) -> u16 {
        self.start
    }

    #[must_use]
    /// Returns the last value included in the interval.
    pub const fn end(self) -> u16 {
        self.end
    }
}

/// Owned inputs for one deterministic single-chunk comparison.
///
/// `array_a` and `array_b` are strictly increasing. Each bitmap and run list
/// represents the same values as its corresponding array.
pub struct CaseData {
    name: &'static str,
    array_a: Vec<u16>,
    array_b: Vec<u16>,
    bitmap_a: Box<Bitmap>,
    bitmap_b: Box<Bitmap>,
    runs_a: Vec<Run>,
    runs_b: Vec<Run>,
}

impl CaseData {
    #[must_use]
    /// Returns the stable case name accepted by `bitmap-probe`.
    pub const fn name(&self) -> &'static str {
        self.name
    }

    #[must_use]
    /// Returns the first strictly increasing array.
    pub fn array_a(&self) -> &[u16] {
        &self.array_a
    }

    #[must_use]
    /// Returns the second strictly increasing array.
    pub fn array_b(&self) -> &[u16] {
        &self.array_b
    }

    #[must_use]
    /// Returns the first fixed bitmap.
    pub fn bitmap_a(&self) -> &Bitmap {
        &self.bitmap_a
    }

    #[must_use]
    /// Returns the second fixed bitmap.
    pub fn bitmap_b(&self) -> &Bitmap {
        &self.bitmap_b
    }

    #[must_use]
    /// Returns the first sorted, non-overlapping run list.
    pub fn runs_a(&self) -> &[Run] {
        &self.runs_a
    }

    #[must_use]
    /// Returns the second sorted, non-overlapping run list.
    pub fn runs_b(&self) -> &[Run] {
        &self.runs_b
    }

    #[must_use]
    /// Computes the intersection cardinality with an independent membership
    /// table used as the correctness oracle.
    pub fn oracle_intersection_cardinality(&self) -> u32 {
        let mut present = vec![false; CONTAINER_BITS];
        for &value in &self.array_a {
            present[usize::from(value)] = true;
        }
        self.array_b
            .iter()
            .filter(|&&value| present[usize::from(value)])
            .count() as u32
    }

    #[must_use]
    /// Counts the intersection by merging the case's canonical arrays.
    pub fn array_intersection_cardinality(&self) -> u32 {
        topic036_array_and_count(&self.array_a, &self.array_b)
    }

    #[must_use]
    /// Counts the intersection by scanning the case's complete bitmaps.
    pub fn bitmap_intersection_cardinality(&self) -> u32 {
        topic036_bitmap_and_count(&self.bitmap_a, &self.bitmap_b)
    }

    #[must_use]
    /// Counts the intersection by merging the case's canonical run lists.
    pub fn run_intersection_cardinality(&self) -> u32 {
        topic036_run_and_count(&self.runs_a, &self.runs_b)
    }
}

#[must_use]
/// Splits an unsigned 32-bit identifier into its high and low 16-bit halves.
///
/// A Roaring directory uses the high half as its chunk key. The selected
/// container stores the low half.
pub const fn split_u32_id(value: u32) -> (u16, u16) {
    ((value >> 16) as u16, value as u16)
}

#[must_use]
/// Builds a fixed bitmap from arbitrary low values.
///
/// Duplicate and unordered values are harmless because setting a bit is
/// idempotent.
pub fn bitmap_from_values(values: &[u16]) -> Box<Bitmap> {
    let mut words = Box::new([0_u64; BITMAP_WORDS]);
    for &value in values {
        let index = usize::from(value);
        words[index / u64::BITS as usize] |= 1_u64 << (index % u64::BITS as usize);
    }
    words
}

#[must_use]
/// Reports whether a fixed bitmap contains `value`.
pub fn bitmap_contains(bitmap: &Bitmap, value: u16) -> bool {
    let index = usize::from(value);
    bitmap[index / u64::BITS as usize] & (1_u64 << (index % u64::BITS as usize)) != 0
}

// The topic-qualified exported name is unique in this workspace. Keeping the
// symbol stable lets the measurement receipt identify the linked kernel.
#[inline(never)]
#[unsafe(no_mangle)]
fn topic036_array_and_count(a: &[u16], b: &[u16]) -> u32 {
    let mut a_index = 0_usize;
    let mut b_index = 0_usize;
    let mut count = 0_u32;

    while a_index < a.len() && b_index < b.len() {
        match a[a_index].cmp(&b[b_index]) {
            std::cmp::Ordering::Less => a_index += 1,
            std::cmp::Ordering::Greater => b_index += 1,
            std::cmp::Ordering::Equal => {
                count += 1;
                a_index += 1;
                b_index += 1;
            }
        }
    }
    count
}

// The topic-qualified exported name is unique in this workspace. Keeping the
// symbol stable lets the measurement receipt identify the linked kernel.
#[inline(never)]
#[unsafe(no_mangle)]
fn topic036_bitmap_and_count(a: &Bitmap, b: &Bitmap) -> u32 {
    a.iter()
        .zip(b)
        .map(|(&left, &right)| (left & right).count_ones())
        .sum()
}

// The topic-qualified exported name is unique in this workspace. Keeping the
// symbol stable lets the measurement receipt identify the linked kernel.
#[inline(never)]
#[unsafe(no_mangle)]
fn topic036_run_and_count(a: &[Run], b: &[Run]) -> u32 {
    let mut a_index = 0_usize;
    let mut b_index = 0_usize;
    let mut count = 0_u32;

    while a_index < a.len() && b_index < b.len() {
        let a_start = u32::from(a[a_index].start);
        let b_start = u32::from(b[b_index].start);
        let a_end = u32::from(a[a_index].end);
        let b_end = u32::from(b[b_index].end);
        let overlap_start = a_start.max(b_start);
        let overlap_end = a_end.min(b_end);

        if overlap_start <= overlap_end {
            count += overlap_end - overlap_start + 1;
        }
        if a_end <= b_end {
            a_index += 1;
        }
        if b_end <= a_end {
            b_index += 1;
        }
    }
    count
}

#[must_use]
/// Returns the portable array-container payload size for `cardinality` values.
///
/// Directory entries, offsets, allocator metadata, and padding are excluded.
pub const fn array_payload_bytes(cardinality: usize) -> usize {
    assert!(cardinality <= CONTAINER_BITS);
    2 * cardinality
}

#[must_use]
/// Returns the fixed portable bitmap-container payload size of 8,192 bytes.
///
/// Directory entries, offsets, allocator metadata, and padding are excluded.
pub const fn bitmap_payload_bytes() -> usize {
    BITMAP_WORDS * size_of::<u64>()
}

#[must_use]
/// Returns `2 + 4 * run_count`, the portable run-container payload size.
///
/// The two-byte run count precedes one `(start, length minus one)` pair per
/// run. The formula excludes directory entries, offsets, allocator metadata,
/// and padding. A zero-run payload is arithmetic only because portable Roaring
/// omits empty containers.
pub const fn run_payload_bytes(run_count: usize) -> usize {
    assert!(run_count <= CONTAINER_BITS / 2);
    2 + 4 * run_count
}

#[must_use]
/// Constructs one deterministic comparison case, or returns `None` for an
/// unknown case name.
pub fn make_case(name: &str) -> Option<CaseData> {
    let (stable_name, a, b) = match name {
        "tiny16" => {
            let a: Vec<u16> = (0..16_u32).map(|index| (index * 4_000) as u16).collect();
            let b = (0..8_usize)
                .map(|index| a[index * 2])
                .chain((0..8_u32).map(|index| (index * 4_000 + 1) as u16))
                .collect();
            ("tiny16", a, b)
        }
        "sparse256" => {
            let a: Vec<u16> = (0..256_u32).map(|index| (index * 200) as u16).collect();
            let b = (0..128_usize)
                .map(|index| a[index * 2])
                .chain((0..128_u32).map(|index| (index * 200 + 1) as u16))
                .collect();
            ("sparse256", a, b)
        }
        "threshold4096" => {
            let a: Vec<u16> = (0..4_096_u32).map(|index| (index * 16) as u16).collect();
            let b = (0..2_048_usize)
                .map(|index| a[index * 2])
                .chain((0..2_048_u32).map(|index| (index * 16 + 1) as u16))
                .collect();
            ("threshold4096", a, b)
        }
        "dense32768" => {
            let a: Vec<u16> = (0..32_768_u32).map(|index| (index * 2) as u16).collect();
            let b = (0..16_384_usize)
                .map(|index| a[index])
                .chain((0..16_384_u32).map(|index| (index * 2 + 1) as u16))
                .collect();
            ("dense32768", a, b)
        }
        "runs64" => {
            let mut a = Vec::with_capacity(32_768);
            let mut b = Vec::with_capacity(32_768);
            for run_index in 0..64_u32 {
                let base = run_index * 1_024;
                a.extend((base..base + 512).map(|value| value as u16));
                b.extend((base + 256..base + 768).map(|value| value as u16));
            }
            ("runs64", a, b)
        }
        _ => return None,
    };

    Some(finish_case(stable_name, a, b))
}

fn finish_case(name: &'static str, mut array_a: Vec<u16>, mut array_b: Vec<u16>) -> CaseData {
    array_a.sort_unstable();
    array_a.dedup();
    array_b.sort_unstable();
    array_b.dedup();
    let bitmap_a = bitmap_from_values(&array_a);
    let bitmap_b = bitmap_from_values(&array_b);
    let runs_a = runs_from_sorted_unique(&array_a);
    let runs_b = runs_from_sorted_unique(&array_b);

    CaseData {
        name,
        array_a,
        array_b,
        bitmap_a,
        bitmap_b,
        runs_a,
        runs_b,
    }
}

fn runs_from_sorted_unique(values: &[u16]) -> Vec<Run> {
    let Some((&first, tail)) = values.split_first() else {
        return Vec::new();
    };

    let mut result = Vec::new();
    let mut start = first;
    let mut previous = first;
    for &value in tail {
        if u32::from(value) == u32::from(previous) + 1 {
            previous = value;
        } else {
            result.push(Run {
                start,
                end: previous,
            });
            start = value;
            previous = value;
        }
    }
    result.push(Run {
        start,
        end: previous,
    });
    result
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn all_representations_match_the_oracle() {
        for name in CASE_NAMES {
            let case = make_case(name).expect("listed case must exist");
            let expected = case.oracle_intersection_cardinality();
            assert_eq!(
                topic036_array_and_count(case.array_a(), case.array_b()),
                expected,
                "array case {name}"
            );
            assert_eq!(
                topic036_bitmap_and_count(case.bitmap_a(), case.bitmap_b()),
                expected,
                "bitmap case {name}"
            );
            assert_eq!(
                topic036_run_and_count(case.runs_a(), case.runs_b()),
                expected,
                "run case {name}"
            );
        }
    }

    #[test]
    fn deterministic_case_contracts_do_not_drift() {
        let expected = [
            ("tiny16", 16, 16, 8, 16, 12, 64, 16_384, 116),
            ("sparse256", 256, 256, 128, 256, 192, 1_024, 16_384, 1_796),
            (
                "threshold4096",
                4_096,
                4_096,
                2_048,
                4_096,
                3_072,
                16_384,
                16_384,
                28_676,
            ),
            (
                "dense32768",
                32_768,
                32_768,
                16_384,
                32_768,
                1,
                131_072,
                16_384,
                131_080,
            ),
            (
                "runs64", 32_768, 32_768, 16_384, 64, 64, 131_072, 16_384, 516,
            ),
        ];

        for (name, card_a, card_b, intersection, runs_a, runs_b, arrays, bitmaps, runs) in expected
        {
            let case = make_case(name).expect("listed case must exist");
            assert_eq!(case.array_a().len(), card_a);
            assert_eq!(case.array_b().len(), card_b);
            assert_eq!(case.oracle_intersection_cardinality(), intersection);
            assert_eq!(case.runs_a().len(), runs_a);
            assert_eq!(case.runs_b().len(), runs_b);
            assert_eq!(
                array_payload_bytes(card_a) + array_payload_bytes(card_b),
                arrays
            );
            assert_eq!(2 * bitmap_payload_bytes(), bitmaps);
            assert_eq!(run_payload_bytes(runs_a) + run_payload_bytes(runs_b), runs);
        }
    }

    #[test]
    fn terminal_run_endpoint_does_not_overflow() {
        let values = [0, 1, u16::MAX - 1, u16::MAX];
        let runs = runs_from_sorted_unique(&values);
        assert_eq!(
            runs,
            [
                Run { start: 0, end: 1 },
                Run {
                    start: u16::MAX - 1,
                    end: u16::MAX,
                },
            ]
        );
        assert_eq!(runs[1].cardinality(), 2);
        assert_eq!(topic036_run_and_count(&runs[1..], &runs[1..]), 2);
    }

    #[test]
    fn exact_payload_crossovers_are_explicit() {
        assert_eq!(array_payload_bytes(4_096), bitmap_payload_bytes());
        assert!(run_payload_bytes(2_047) < bitmap_payload_bytes());
        assert!(run_payload_bytes(2_048) > bitmap_payload_bytes());
    }

    #[test]
    fn split_and_membership_cover_unsigned_boundaries() {
        assert_eq!(split_u32_id(0), (0, 0));
        assert_eq!(split_u32_id(0x1234_abcd), (0x1234, 0xabcd));
        assert_eq!(split_u32_id(u32::MAX), (u16::MAX, u16::MAX));
        let bitmap = bitmap_from_values(&[0, 0xabcd, u16::MAX]);
        assert!(bitmap_contains(&bitmap, 0));
        assert!(bitmap_contains(&bitmap, 0xabcd));
        assert!(bitmap_contains(&bitmap, u16::MAX));
        assert!(!bitmap_contains(&bitmap, 1));
    }

    #[test]
    fn run_constructor_rejects_reversed_endpoints() {
        assert_eq!(Run::new(7, 9), Some(Run { start: 7, end: 9 }));
        assert_eq!(Run::new(9, 7), None);
    }
}
