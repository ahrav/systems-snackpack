//! Executable models for filesystem crash semantics.
//!
//! Filesystem recovery and application durability are separate contracts. This
//! crate models the dependency chain for replacing one file and keeps four
//! simplified write-cost calculations checked in code. The accompanying Linux
//! experiment observes deterministic process exits on a still-running kernel;
//! it does not simulate power loss or filesystem replay.
//!
//! # Record oracle
//!
//! The Rust model and native probe use the same byte-order-independent 8 KiB
//! record layout:
//!
//! | Byte range | Contents |
//! | --- | --- |
//! | `0..8` | Magic bytes `COWCUT01` |
//! | `8..16` | Generation as a little-endian `u64` |
//! | `16..8184` | Rust caller-selected fill; native `O` or `N` fill |
//! | `8184..8192` | Little-endian FNV-1a checksum of bytes `0..8184` |
//!
//! The classifier accepts generation 41 as old and generation 42 as new only
//! after the length, magic, and checksum pass. Every other generation is
//! invalid even when its checksum is valid.
//!
//! # Example
//!
//! ```
//! use filesystem_crash_semantics::{
//!     CutPoint, PersistentState, classify_record, encode_record,
//!     expected_live_observation,
//! };
//!
//! let record = encode_record(42, b'N');
//! assert_eq!(classify_record(&record), PersistentState::New(42));
//!
//! let observed = expected_live_observation(CutPoint::AfterRename);
//! assert_eq!(observed.current, PersistentState::New(42));
//! assert!(!observed.temp_present);
//! ```

/// The record length required by the Rust classifier and native probe.
pub const RECORD_BYTES: usize = 8 * 1024;

const MAGIC: &[u8; 8] = b"COWCUT01";
const CHECKSUM_BYTES: usize = 8;
const GENERATION_OFFSET: usize = MAGIC.len();
const CHECKSUM_OFFSET: usize = RECORD_BYTES - CHECKSUM_BYTES;

/// A deterministic process-exit point in the replacement protocol.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum CutPoint {
    /// The new record was written to the temporary file but not synchronized.
    AfterWrite,
    /// The temporary file's synchronization call completed successfully.
    AfterFileSync,
    /// The temporary pathname replaced the destination pathname.
    AfterRename,
    /// The parent directory's synchronization call completed successfully.
    AfterDirectorySync,
    /// Every required step completed and the operation may be acknowledged.
    Complete,
}

/// The checksum-validated application state recovered from one record.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum PersistentState {
    /// The classifier decoded initialized generation 41.
    Old(u64),
    /// The classifier decoded replacement generation 42.
    New(u64),
    /// Length, magic, checksum, or supported-generation validation failed.
    Invalid,
}

/// State visible after the experiment process exits while Linux remains live.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct LiveObservation {
    /// Checksum-validated state at the destination pathname.
    pub current: PersistentState,
    /// Whether the same-directory temporary pathname remains present.
    pub temp_present: bool,
    /// Whether every persistence step required before acknowledgement completed.
    pub acknowledgeable: bool,
}

/// Returns the live-kernel observation required by the deterministic harness.
///
/// These states describe process termination on the tested mounted filesystem.
/// They are not predictions for power loss or journal replay.
#[must_use]
pub const fn expected_live_observation(cut: CutPoint) -> LiveObservation {
    match cut {
        CutPoint::AfterWrite | CutPoint::AfterFileSync => LiveObservation {
            current: PersistentState::Old(41),
            temp_present: true,
            acknowledgeable: false,
        },
        CutPoint::AfterRename => LiveObservation {
            current: PersistentState::New(42),
            temp_present: false,
            acknowledgeable: false,
        },
        CutPoint::AfterDirectorySync | CutPoint::Complete => LiveObservation {
            current: PersistentState::New(42),
            temp_present: false,
            acknowledgeable: true,
        },
    }
}

/// Encodes the oracle magic, generation, fill, and checksum into one record.
#[must_use]
pub fn encode_record(generation: u64, fill: u8) -> [u8; RECORD_BYTES] {
    let mut record = [fill; RECORD_BYTES];
    record[..MAGIC.len()].copy_from_slice(MAGIC);
    record[GENERATION_OFFSET..GENERATION_OFFSET + 8].copy_from_slice(&generation.to_le_bytes());
    let checksum = fnv1a64(&record[..CHECKSUM_OFFSET]);
    record[CHECKSUM_OFFSET..].copy_from_slice(&checksum.to_le_bytes());
    record
}

/// Classifies a record only after its exact length, magic, and checksum pass.
///
/// Generation 41 maps to [`PersistentState::Old`] and generation 42 maps to
/// [`PersistentState::New`]; every other generation maps to
/// [`PersistentState::Invalid`].
#[must_use]
pub fn classify_record(record: &[u8]) -> PersistentState {
    if record.len() != RECORD_BYTES || &record[..MAGIC.len()] != MAGIC {
        return PersistentState::Invalid;
    }

    let generation = u64::from_le_bytes(
        record[GENERATION_OFFSET..GENERATION_OFFSET + 8]
            .try_into()
            .expect("the checked fixed-size record contains eight generation bytes"),
    );
    let stored_checksum = u64::from_le_bytes(
        record[CHECKSUM_OFFSET..]
            .try_into()
            .expect("the checked fixed-size record contains eight checksum bytes"),
    );
    if fnv1a64(&record[..CHECKSUM_OFFSET]) != stored_checksum {
        return PersistentState::Invalid;
    }

    match generation {
        41 => PersistentState::Old(generation),
        42 => PersistentState::New(generation),
        _ => PersistentState::Invalid,
    }
}

/// Computes the 64-bit Fowler-Noll-Vo 1a checksum used by the state oracle.
///
/// Wrapping multiplication matches the native probe's unsigned C arithmetic.
/// The checksum detects the experiment's corruption control; it does not
/// authenticate data or repair damaged media.
#[must_use]
pub fn fnv1a64(bytes: &[u8]) -> u64 {
    bytes.iter().fold(14_695_981_039_346_656_037, |hash, byte| {
        (hash ^ u64::from(*byte)).wrapping_mul(1_099_511_628_211)
    })
}

/// Returns simplified filesystem-issued bytes for metadata journaling.
///
/// Ordered mode counts user data once, metadata twice, and journal control
/// traffic once. Full data journaling counts user data twice as well.
/// The model omits alignment, aggregation, allocation, replication, and device
/// amplification.
///
/// # Errors
///
/// Returns `None` if any multiplication or addition exceeds `u128`.
#[must_use]
pub fn journal_issued_bytes(
    data_bytes: u128,
    metadata_bytes: u128,
    control_bytes: u128,
    full_data_journal: bool,
) -> Option<u128> {
    let data_copies: u128 = if full_data_journal { 2 } else { 1 };
    data_copies
        .checked_mul(data_bytes)?
        .checked_add(2_u128.checked_mul(metadata_bytes)?)?
        .checked_add(control_bytes)
}

/// Returns simplified filesystem-issued bytes for a tree copy-on-write update.
///
/// The result adds new data, copied ancestor nodes, auxiliary metadata, and
/// root-publication traffic. It does not estimate device or flash writes.
///
/// # Errors
///
/// Returns `None` if any multiplication or addition exceeds `u128`.
#[must_use]
pub fn cow_issued_bytes(
    data_bytes: u128,
    copied_nodes: u128,
    node_bytes: u128,
    auxiliary_bytes: u128,
    root_bytes: u128,
) -> Option<u128> {
    data_bytes
        .checked_add(copied_nodes.checked_mul(node_bytes)?)?
        .checked_add(auxiliary_bytes)?
        .checked_add(root_bytes)
}

/// Returns simplified synchronous-log completion time in milliseconds.
///
/// `service_mib_per_second` uses `2^20` bytes per second. The result adds
/// transfer time to one stable-storage barrier and omits queueing and
/// filesystem work. Accepted finite inputs can still produce
/// `f64::INFINITY`; the result is not revalidated after arithmetic.
///
/// # Errors
///
/// Returns `None` if:
///
/// - `service_mib_per_second` is non-finite or less than or equal to zero.
/// - `barrier_ms` is non-finite or negative.
#[must_use]
pub fn sync_log_latency_ms(
    log_bytes: u128,
    service_mib_per_second: f64,
    barrier_ms: f64,
) -> Option<f64> {
    if !service_mib_per_second.is_finite()
        || service_mib_per_second <= 0.0
        || !barrier_ms.is_finite()
        || barrier_ms < 0.0
    {
        return None;
    }
    let transfer_ms = log_bytes as f64 / (service_mib_per_second * 1024.0 * 1024.0) * 1000.0;
    Some(transfer_ms + barrier_ms)
}

/// Adds `[write, file sync, rename, directory sync]` latency in milliseconds.
///
/// Accepted finite phases can sum to `f64::INFINITY`; the result is not
/// revalidated after addition.
///
/// # Errors
///
/// Returns `None` if any phase is negative or non-finite.
#[must_use]
pub fn replacement_latency_ms(phases_ms: [f64; 4]) -> Option<f64> {
    phases_ms
        .iter()
        .all(|value| value.is_finite() && *value >= 0.0)
        .then(|| phases_ms.iter().sum())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn record_oracle_accepts_old_and_new() {
        assert_eq!(
            classify_record(&encode_record(41, b'O')),
            PersistentState::Old(41)
        );
        assert_eq!(
            classify_record(&encode_record(42, b'N')),
            PersistentState::New(42)
        );
    }

    #[test]
    fn record_oracle_rejects_corruption_and_unknown_generation() {
        let mut corrupt = encode_record(42, b'N');
        corrupt[128] ^= 0xff;
        assert_eq!(classify_record(&corrupt), PersistentState::Invalid);
        assert_eq!(
            classify_record(&encode_record(43, b'?')),
            PersistentState::Invalid
        );
    }

    #[test]
    fn cut_points_cross_acknowledgement_only_after_directory_sync() {
        for cut in [
            CutPoint::AfterWrite,
            CutPoint::AfterFileSync,
            CutPoint::AfterRename,
        ] {
            assert!(!expected_live_observation(cut).acknowledgeable);
        }
        assert!(expected_live_observation(CutPoint::AfterDirectorySync).acknowledgeable);
        assert!(expected_live_observation(CutPoint::Complete).acknowledgeable);
    }

    #[test]
    fn worked_byte_models_match_the_lesson() {
        let kib = 1024_u128;
        assert_eq!(
            journal_issued_bytes(1024 * kib, 64 * kib, 8 * kib, false),
            Some(1160 * kib)
        );
        assert_eq!(
            journal_issued_bytes(1024 * kib, 64 * kib, 8 * kib, true),
            Some(2184 * kib)
        );
        assert_eq!(
            cow_issued_bytes(4 * kib, 4, 16 * kib, 32 * kib, 4 * kib),
            Some(104 * kib)
        );
    }

    #[test]
    fn byte_models_reject_overflow() {
        assert_eq!(journal_issued_bytes(u128::MAX, 0, 0, true), None);
        assert_eq!(cow_issued_bytes(1, u128::MAX, 2, 0, 0), None);
    }

    #[test]
    fn worked_latency_models_match_the_lesson() {
        let log = sync_log_latency_ms(64 * 1024, 500.0, 0.8).expect("valid model");
        assert!((log - 0.925).abs() < 1e-12);
        let replacement = replacement_latency_ms([0.35, 4.80, 0.06, 0.75]).expect("valid model");
        assert!((replacement - 5.96).abs() < 1e-12);
    }

    #[test]
    fn invalid_latency_inputs_fail_closed() {
        assert_eq!(sync_log_latency_ms(1, 0.0, 1.0), None);
        assert_eq!(replacement_latency_ms([0.0, -1.0, 0.0, 0.0]), None);
    }
}
