//! Static `rank1` representations with one explicit query contract.
//!
//! [`CompactRank`] stores a word-aligned bitvector with a two-level count
//! directory. [`PrefixRank`] stores every prefix answer and serves as a simple
//! oracle. Both define `rank1(pos)` as the number of one bits in `[0, pos)`.
//! The compact directory adds metadata linear in the payload size, so this
//! experiment demonstrates a compact static layout rather than a formally
//! succinct `N + o(N)` representation.
//!
//! ```
//! use systems_snackpack_topic_009::{CompactRank, PrefixRank};
//!
//! let words = vec![0b1011_u64];
//! let compact = CompactRank::from_words(words.clone())?;
//! let prefix = PrefixRank::from_words(&words)?;
//!
//! assert_eq!(compact.rank1(3), Some(2));
//! assert_eq!(compact.rank1(64), Some(3));
//! assert_eq!(compact.rank1(65), None);
//! assert_eq!(compact.rank1(3), prefix.rank1(3));
//! # Ok::<(), systems_snackpack_topic_009::BuildError>(())
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

use std::{fmt, mem::size_of};

const WORD_BITS: usize = u64::BITS as usize;
const SUPERBLOCK_WORDS: usize = 8;

/// Maximum word count supported by 32-bit cumulative counts.
pub const MAX_WORDS: usize = (u32::MAX as usize) / WORD_BITS;

/// Seed for the deterministic experiment dataset.
///
/// The bench and the equivalence example both derive their input from this
/// seed through [`dataset_words`], so the exhaustively verified dataset and
/// the timed dataset are the same bytes for a given length.
pub const DATASET_SEED: u64 = 0x243f_6a88_85a3_08d3;

/// Advances a SplitMix64 state and returns its next output.
pub fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

/// Generates the deterministic experiment dataset for `bit_len` bits.
///
/// Produces `bit_len / 64` complete words from [`DATASET_SEED`]. Both
/// experiment binaries must build their input through this function so the
/// verified and timed datasets stay byte-identical.
///
/// # Panics
///
/// Panics unless `bit_len` is a multiple of 64: a partial trailing word
/// cannot be represented, and silently flooring would let a caller that
/// retains the requested length issue positions the generated data does
/// not contain.
pub fn dataset_words(bit_len: usize) -> Vec<u64> {
    assert_eq!(
        bit_len % WORD_BITS,
        0,
        "dataset bit length must be a multiple of {WORD_BITS}, got {bit_len}"
    );
    let mut state = DATASET_SEED;
    (0..bit_len / WORD_BITS)
        .map(|_| splitmix64(&mut state))
        .collect()
}

/// A failure to build a rank representation.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum BuildError {
    /// The input length cannot be expressed in bits by `usize`.
    LengthOverflow {
        /// Number of input words.
        words: usize,
    },
    /// The input can contain more one bits than a `u32` count can represent.
    TooLong {
        /// Number of input words.
        words: usize,
        /// Largest supported number of input words.
        max_words: usize,
    },
}

impl fmt::Display for BuildError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::LengthOverflow { words } => {
                write!(formatter, "{words} words overflow a usize bit length")
            }
            Self::TooLong { words, max_words } => write!(
                formatter,
                "{words} words exceed the u32 rank-count limit of {max_words} words"
            ),
        }
    }
}

impl std::error::Error for BuildError {}

/// A word-aligned bitvector with two levels of rank metadata.
///
/// One absolute `u32` count is stored per eight input words. One `u16` count
/// per word records the number of one bits between the superblock start and
/// that word. The fixed directory adds `0.3125` metadata bits per represented
/// bit for complete eight-word superblocks. Its overhead is `Theta(N)`, not
/// `o(N)`.
#[derive(Clone, Debug)]
pub struct CompactRank {
    words: Vec<u64>,
    superblocks: Vec<u32>,
    subblocks: Vec<u16>,
    ones: u32,
}

impl CompactRank {
    /// Builds a rank directory over complete 64-bit words.
    ///
    /// The input is moved into the representation. Bit position zero is the
    /// least-significant bit of `words[0]`.
    ///
    /// # Errors
    ///
    /// - Returns [`BuildError::LengthOverflow`] when converting the word count
    ///   to bits overflows `usize`. On a 32-bit target, this error takes
    ///   precedence once the product no longer fits.
    /// - Returns [`BuildError::TooLong`] when that conversion succeeds but the
    ///   input could contain more one bits than a `u32` rank can represent.
    pub fn from_words(words: Vec<u64>) -> Result<Self, BuildError> {
        validate_word_count(words.len())?;

        let mut superblocks = Vec::with_capacity(words.len().div_ceil(SUPERBLOCK_WORDS));
        let mut subblocks = Vec::with_capacity(words.len());
        let mut total = 0_u32;

        for (word_index, &word) in words.iter().enumerate() {
            if word_index % SUPERBLOCK_WORDS == 0 {
                superblocks.push(total);
            }
            let superblock_count = superblocks[word_index / SUPERBLOCK_WORDS];
            let within_superblock = total - superblock_count;
            debug_assert!(within_superblock <= (SUPERBLOCK_WORDS as u32 - 1) * u64::BITS);
            subblocks.push(within_superblock as u16);
            total += word.count_ones();
        }

        Ok(Self {
            words,
            superblocks,
            subblocks,
            ones: total,
        })
    }

    /// Returns the number of represented bits.
    pub fn len(&self) -> usize {
        self.words.len() * WORD_BITS
    }

    /// Reports whether the represented bitvector is empty.
    pub fn is_empty(&self) -> bool {
        self.words.is_empty()
    }

    /// Returns the total number of one bits.
    pub const fn ones(&self) -> u32 {
        self.ones
    }

    /// Returns the logical heap bytes used by payload and directories.
    ///
    /// This excludes vector handles, unused capacity, allocator metadata, and
    /// page rounding. The focused experiment uses this structural-byte sum as
    /// its space-comparison boundary.
    pub fn logical_bytes(&self) -> usize {
        self.words.len() * size_of::<u64>()
            + self.superblocks.len() * size_of::<u32>()
            + self.subblocks.len() * size_of::<u16>()
    }

    /// Counts one bits in the half-open prefix `[0, pos)`.
    ///
    /// Returns `None` when `pos` exceeds [`Self::len`]. The endpoint at
    /// `pos == self.len()` is valid and returns [`Self::ones`].
    pub fn rank1(&self, pos: usize) -> Option<u32> {
        if pos > self.len() {
            return None;
        }
        if pos == self.len() {
            return Some(self.ones);
        }

        let word_index = pos / WORD_BITS;
        let bit_offset = pos % WORD_BITS;
        let lower_mask = if bit_offset == 0 {
            0
        } else {
            u64::MAX >> (WORD_BITS - bit_offset)
        };
        Some(
            self.superblocks[word_index / SUPERBLOCK_WORDS]
                + u32::from(self.subblocks[word_index])
                + (self.words[word_index] & lower_mask).count_ones(),
        )
    }
}

/// A complete `u32` prefix-answer table used as a rank oracle.
///
/// The table contains one entry for every bit position plus the endpoint. It
/// is intentionally much larger than the source bitvector. Adjacent prefix
/// differences recover every source bit, so the logical-byte comparison does
/// not charge this representation for a second payload copy.
#[derive(Clone, Debug)]
pub struct PrefixRank {
    prefix: Vec<u32>,
}

impl PrefixRank {
    /// Builds every half-open prefix answer for complete 64-bit words.
    ///
    /// # Errors
    ///
    /// - Returns [`BuildError::LengthOverflow`] when converting the word count
    ///   to bits overflows `usize`. On a 32-bit target, this error takes
    ///   precedence once the product no longer fits.
    /// - Returns [`BuildError::TooLong`] when that conversion succeeds but the
    ///   input could contain more one bits than a `u32` rank can represent.
    pub fn from_words(words: &[u64]) -> Result<Self, BuildError> {
        let bit_len = validate_word_count(words.len())?;
        let mut prefix = Vec::with_capacity(bit_len + 1);
        let mut total = 0_u32;
        prefix.push(total);
        for &word in words {
            for bit in 0..WORD_BITS {
                total += ((word >> bit) & 1) as u32;
                prefix.push(total);
            }
        }
        Ok(Self { prefix })
    }

    /// Returns the number of represented bits.
    pub fn len(&self) -> usize {
        self.prefix.len() - 1
    }

    /// Reports whether the represented bitvector is empty.
    pub fn is_empty(&self) -> bool {
        self.len() == 0
    }

    /// Returns the total number of one bits.
    pub fn ones(&self) -> u32 {
        self.prefix[self.len()]
    }

    /// Returns the logical heap bytes used by the prefix table.
    ///
    /// This excludes the vector handle, unused capacity, allocator metadata,
    /// and page rounding.
    pub fn logical_bytes(&self) -> usize {
        self.prefix.len() * size_of::<u32>()
    }

    /// Counts one bits in the half-open prefix `[0, pos)`.
    ///
    /// Returns `None` when `pos` exceeds [`Self::len`].
    pub fn rank1(&self, pos: usize) -> Option<u32> {
        self.prefix.get(pos).copied()
    }
}

/// Preserves a named compact-query boundary in linked-binary disassembly.
///
/// Returns zero when `pos` exceeds [`CompactRank::len`]. The endpoint at
/// `pos == index.len()` remains valid and returns [`CompactRank::ones`].
#[inline(never)]
// The topic-specific exported name is unique within this workspace.
#[unsafe(export_name = "topic009_inspect_compact_rank")]
pub fn inspect_compact_rank(index: &CompactRank, pos: usize) -> u32 {
    index.rank1(pos).unwrap_or(0)
}

/// Preserves a named prefix-query boundary in linked-binary disassembly.
///
/// Returns zero when `pos` exceeds [`PrefixRank::len`]. The endpoint at
/// `pos == index.len()` remains valid and returns [`PrefixRank::ones`].
#[inline(never)]
// The topic-specific exported name is unique within this workspace.
#[unsafe(export_name = "topic009_inspect_prefix_rank")]
pub fn inspect_prefix_rank(index: &PrefixRank, pos: usize) -> u32 {
    index.rank1(pos).unwrap_or(0)
}

fn validate_word_count(words: usize) -> Result<usize, BuildError> {
    let bit_len = words
        .checked_mul(WORD_BITS)
        .ok_or(BuildError::LengthOverflow { words })?;
    if words > MAX_WORDS {
        return Err(BuildError::TooLong {
            words,
            max_words: MAX_WORDS,
        });
    }
    Ok(bit_len)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn assert_parity(words: Vec<u64>) {
        let compact = CompactRank::from_words(words.clone()).unwrap();
        let prefix = PrefixRank::from_words(&words).unwrap();
        assert_eq!(compact.len(), prefix.len());
        assert_eq!(compact.ones(), prefix.ones());
        for pos in 0..=compact.len() {
            assert_eq!(compact.rank1(pos), prefix.rank1(pos), "position {pos}");
        }
        assert_eq!(compact.rank1(compact.len() + 1), None);
        assert_eq!(prefix.rank1(prefix.len() + 1), None);
    }

    #[test]
    fn empty_input_has_one_valid_prefix() {
        assert_parity(Vec::new());
    }

    #[test]
    fn all_zero_and_all_one_boundaries_match() {
        assert_parity(vec![0; 17]);
        assert_parity(vec![u64::MAX; 17]);
    }

    #[test]
    fn superblock_and_word_boundaries_match() {
        let mut words = vec![0; 17];
        words[0] = 1;
        words[7] = 1 << 63;
        words[8] = 1;
        words[16] = u64::MAX;
        assert_parity(words);
    }

    #[test]
    fn deterministic_random_input_matches_exhaustively() {
        assert_parity(dataset_words(64 * WORD_BITS));
    }

    #[test]
    #[should_panic(expected = "dataset bit length must be a multiple of 64")]
    fn dataset_rejects_partial_trailing_word() {
        dataset_words(65);
    }

    #[test]
    fn logical_bytes_match_the_fixed_layout() {
        let compact = CompactRank::from_words(vec![0; 16]).unwrap();
        let prefix = PrefixRank::from_words(&[0; 16]).unwrap();
        assert_eq!(compact.logical_bytes(), 16 * 8 + 2 * 4 + 16 * 2);
        assert_eq!(prefix.logical_bytes(), (16 * 64 + 1) * 4);
    }

    #[cfg(target_pointer_width = "64")]
    #[test]
    fn rejects_word_count_beyond_u32_rank_range() {
        assert_eq!(
            validate_word_count(MAX_WORDS + 1),
            Err(BuildError::TooLong {
                words: MAX_WORDS + 1,
                max_words: MAX_WORDS,
            })
        );
    }
}
