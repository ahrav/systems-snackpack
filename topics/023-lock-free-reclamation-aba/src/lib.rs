//! Bounded ABA witness for separating identity from memory reclamation.
//!
//! The fixture keeps two nodes in fixed storage. It forces an `A -> B -> empty
//! -> A` head history, then applies an operation that still expects the first
//! incarnation of A. An index-only compare-and-swap accepts the stale state;
//! a packed generation and index rejects it. No node is freed, so the result
//! demonstrates logical ABA without a use-after-free.
//!
//! The fixture requires a target that supports 64-bit atomic load and
//! compare-exchange operations.

use std::sync::atomic::{AtomicU64, Ordering};

/// Sentinel head index that denotes no reachable node.
pub const EMPTY: u32 = 0;
/// Index that begins and completes the forced `A -> B -> empty -> A` history.
pub const A: u32 = 1;
/// Successor captured by the stale `A` snapshot and removed before its CAS.
pub const B: u32 = 2;

const INDEX_MASK: u64 = u32::MAX as u64;

/// Observations from the raw and tagged arms after the fixed ABA schedule.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct WitnessOutcome {
    /// `run_aba_witness` sets this to true when the final `A` bits match the snapshot.
    pub raw_stale_cas: bool,
    /// `run_aba_witness` sets this to true after the stale update reinstalls `B`.
    pub raw_reintroduced_b: bool,
    /// `run_aba_witness` sets this to false after advancing the generation.
    pub tagged_stale_cas: bool,
    /// `run_aba_witness` returns `3` because the rejected CAS preserves the tag.
    pub tagged_generation: u32,
    /// `run_aba_witness` returns `A` because the rejected CAS preserves the index.
    pub tagged_index: u32,
}

/// Packs one 32-bit generation and one 32-bit index into a single CAS word.
///
/// Packing provides no lifetime protection. A protocol that increments the
/// generation on every relevant head change distinguishes histories only while
/// the generation does not wrap during a stale snapshot's lifetime.
///
/// # Examples
///
/// ```
/// use lock_free_reclamation_aba::{head_generation, head_index, pack_head};
///
/// let head = pack_head(7, 11);
/// assert_eq!(head_generation(head), 7);
/// assert_eq!(head_index(head), 11);
/// ```
pub const fn pack_head(generation: u32, index: u32) -> u64 {
    ((generation as u64) << 32) | index as u64
}

/// Extracts the low 32 bits and discards the generation.
pub const fn head_index(word: u64) -> u32 {
    (word & INDEX_MASK) as u32
}

/// Extracts the high 32 bits and discards the index.
pub const fn head_generation(word: u64) -> u32 {
    (word >> 32) as u32
}

/// Executes a deterministic index-only and tagged ABA comparison.
///
/// All operations run in one thread with `Relaxed` ordering. The fixture tests
/// equality versus identity, not inter-thread ordering or reclamation safety.
///
/// # Panics
///
/// Panics if any of the six scheduled transitions does not observe its
/// specified predecessor.
///
/// # Examples
///
/// ```
/// use lock_free_reclamation_aba::run_aba_witness;
///
/// let result = run_aba_witness();
/// assert!(result.raw_stale_cas);
/// assert!(result.raw_reintroduced_b);
/// assert!(!result.tagged_stale_cas);
/// ```
pub fn run_aba_witness() -> WitnessOutcome {
    let next = [EMPTY, B, EMPTY];

    let raw = AtomicU64::new(u64::from(A));
    let raw_seen = raw.load(Ordering::Relaxed);
    let raw_next = u64::from(next[raw_seen as usize]);
    cas_exact(&raw, u64::from(A), u64::from(B));
    cas_exact(&raw, u64::from(B), u64::from(EMPTY));
    cas_exact(&raw, u64::from(EMPTY), u64::from(A));
    let raw_stale_cas = raw
        .compare_exchange(raw_seen, raw_next, Ordering::Relaxed, Ordering::Relaxed)
        .is_ok();
    let raw_reintroduced_b = raw.load(Ordering::Relaxed) == u64::from(B);

    let tagged = AtomicU64::new(pack_head(0, A));
    let tagged_seen = tagged.load(Ordering::Relaxed);
    let tagged_next = next[head_index(tagged_seen) as usize];
    cas_exact(&tagged, pack_head(0, A), pack_head(1, B));
    cas_exact(&tagged, pack_head(1, B), pack_head(2, EMPTY));
    cas_exact(&tagged, pack_head(2, EMPTY), pack_head(3, A));
    let tagged_stale_cas = tagged
        .compare_exchange(
            tagged_seen,
            pack_head(head_generation(tagged_seen).wrapping_add(1), tagged_next),
            Ordering::Relaxed,
            Ordering::Relaxed,
        )
        .is_ok();
    let tagged_current = tagged.load(Ordering::Relaxed);

    WitnessOutcome {
        raw_stale_cas,
        raw_reintroduced_b,
        tagged_stale_cas,
        tagged_generation: head_generation(tagged_current),
        tagged_index: head_index(tagged_current),
    }
}

// Enforces one fixture transition and panics if the schedule has drifted.
fn cas_exact(head: &AtomicU64, old: u64, new: u64) {
    assert_eq!(
        head.compare_exchange(old, new, Ordering::Relaxed, Ordering::Relaxed),
        Ok(old)
    );
}

#[cfg(test)]
mod tests {
    use super::{A, B, head_generation, head_index, pack_head, run_aba_witness};

    #[test]
    fn raw_control_accepts_stale_identity() {
        let result = run_aba_witness();
        assert!(result.raw_stale_cas);
        assert!(result.raw_reintroduced_b);
    }

    #[test]
    fn generation_rejects_bounded_aba_history() {
        let result = run_aba_witness();
        assert!(!result.tagged_stale_cas);
        assert_eq!((result.tagged_generation, result.tagged_index), (3, A));
    }

    #[test]
    fn packing_round_trips() {
        let value = pack_head(17, B);
        assert_eq!(head_generation(value), 17);
        assert_eq!(head_index(value), B);
    }

    #[test]
    fn generation_bits_repeat_after_wrap() {
        assert_eq!(pack_head(u32::MAX.wrapping_add(1), A), pack_head(0, A));
    }
}
