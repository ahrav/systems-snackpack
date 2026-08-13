//! Portable model of write-ahead log framing and prefix recovery.
//!
//! A write-ahead log (WAL) records a change before the system exposes that
//! change as committed. This crate models the byte-level half of that rule. It
//! encodes numbered, checksummed frames and recovers only the longest valid,
//! contiguous prefix. [`recover_prefix`] rejects damage inside required
//! history but permits an invalid suffix after the caller's required log
//! sequence number.
//!
//! The model does not issue storage commands or claim power-loss durability.
//! The `wal-crash-probe` binary separately exercises `fdatasync`, process
//! termination, and group-commit batching on the host filesystem.

use std::error::Error;
use std::fmt::{self, Display, Formatter};

const MAGIC: &[u8; 4] = b"WAL1";
const VERSION: u16 = 1;
const HEADER_LEN: usize = 40;
const FLAGS_OFFSET: usize = 28;
const CHECKSUM_OFFSET: usize = 32;
const RESERVED_OFFSET: usize = 36;
const GENERATION: u64 = 7;
const MAX_PAYLOAD: usize = 1 << 20;

/// Result of scanning a log for its longest valid, contiguous prefix.
///
/// `valid_lsn` is the last valid log sequence number (LSN). An LSN is a
/// monotonically increasing record position, not a byte offset. Bytes after
/// `valid_bytes` are untrusted and must not be replayed.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Recovery {
    valid_lsn: u64,
    valid_bytes: usize,
    tail_reason: Option<String>,
    semantic_crc32c: u32,
}

impl Recovery {
    /// Returns the last contiguous LSN accepted by recovery, or zero for none.
    #[must_use]
    pub fn valid_lsn(&self) -> u64 {
        self.valid_lsn
    }

    /// Returns the exclusive byte offset of the accepted prefix.
    #[must_use]
    pub fn valid_bytes(&self) -> usize {
        self.valid_bytes
    }

    /// Returns why scanning stopped, or `None` when the input ended cleanly.
    #[must_use]
    pub fn tail_reason(&self) -> Option<&str> {
        self.tail_reason.as_deref()
    }

    /// Returns a CRC-32C digest over the accepted prefix.
    ///
    /// This digest identifies recovered bytes inside the experiment. It is not
    /// a cryptographic commitment.
    #[must_use]
    pub fn semantic_crc32c(&self) -> u32 {
        self.semantic_crc32c
    }
}

/// Error returned when a frame cannot be encoded or required history is bad.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct WalError(String);

impl Display for WalError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        formatter.write_str(&self.0)
    }
}

impl Error for WalError {}

fn put_u16(dst: &mut [u8], offset: usize, value: u16) {
    dst[offset..offset + 2].copy_from_slice(&value.to_le_bytes());
}

fn put_u32(dst: &mut [u8], offset: usize, value: u32) {
    dst[offset..offset + 4].copy_from_slice(&value.to_le_bytes());
}

fn put_u64(dst: &mut [u8], offset: usize, value: u64) {
    dst[offset..offset + 8].copy_from_slice(&value.to_le_bytes());
}

fn get_u16(src: &[u8], offset: usize) -> u16 {
    u16::from_le_bytes(
        src[offset..offset + 2]
            .try_into()
            .expect("the caller checked the fixed header length"),
    )
}

fn get_u32(src: &[u8], offset: usize) -> u32 {
    u32::from_le_bytes(
        src[offset..offset + 4]
            .try_into()
            .expect("the caller checked the fixed header length"),
    )
}

fn get_u64(src: &[u8], offset: usize) -> u64 {
    u64::from_le_bytes(
        src[offset..offset + 8]
            .try_into()
            .expect("the caller checked the fixed header length"),
    )
}

/// Computes the reflected CRC-32C checksum used by the model's frames.
///
/// The named, non-inlined symbol lets host runs retain generated-code evidence.
/// The checksum detects corruption in this experiment; it does not repair data
/// or authenticate an attacker-controlled log.
///
/// # Examples
///
/// ```
/// use wal_crash_consistency::crc32c;
///
/// assert_eq!(crc32c(b"123456789"), 0xe306_9283);
/// ```
#[unsafe(no_mangle)]
#[inline(never)]
#[must_use]
pub fn topic33_crc32c(bytes: &[u8]) -> u32 {
    let mut crc = !0_u32;
    for &byte in bytes {
        crc ^= u32::from(byte);
        for _ in 0..8 {
            let mask = 0_u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (0x82f6_3b78 & mask);
        }
    }
    !crc
}

/// Alias for [`topic33_crc32c`] with a descriptive caller-facing name.
pub use topic33_crc32c as crc32c;

/// Encodes one checksummed frame for the supplied LSN and payload.
///
/// The format fixes generation `7`, flags `0`, and a 40-byte little-endian
/// header so the experiment can enumerate every possible prefix cut.
///
/// # Errors
///
/// Returns an error when `payload` exceeds 1 MiB.
///
/// # Examples
///
/// ```
/// use wal_crash_consistency::{encode_frame, recover_prefix};
///
/// let frame = encode_frame(1, b"committed change")?;
/// let recovered = recover_prefix(&frame, 1)?;
/// assert_eq!(recovered.valid_lsn(), 1);
/// # Ok::<(), wal_crash_consistency::WalError>(())
/// ```
pub fn encode_frame(lsn: u64, payload: &[u8]) -> Result<Vec<u8>, WalError> {
    if payload.len() > MAX_PAYLOAD {
        return Err(WalError(format!(
            "payload_too_large:{}:maximum:{MAX_PAYLOAD}",
            payload.len()
        )));
    }
    let mut out = vec![0_u8; HEADER_LEN + payload.len()];
    out[0..4].copy_from_slice(MAGIC);
    put_u16(&mut out, 4, VERSION);
    put_u16(&mut out, 6, HEADER_LEN as u16);
    put_u64(&mut out, 8, GENERATION);
    put_u64(&mut out, 16, lsn);
    put_u32(&mut out, 24, payload.len() as u32);
    put_u32(&mut out, FLAGS_OFFSET, 0);
    put_u32(&mut out, CHECKSUM_OFFSET, 0);
    put_u32(&mut out, RESERVED_OFFSET, 0);
    out[HEADER_LEN..].copy_from_slice(payload);
    let checksum = crc32c(&out);
    put_u32(&mut out, CHECKSUM_OFFSET, checksum);
    Ok(out)
}

fn inspect_frame(bytes: &[u8], offset: usize, expected_lsn: u64) -> Result<usize, String> {
    let remaining = bytes.len().saturating_sub(offset);
    if remaining < HEADER_LEN {
        return Err(format!("truncated_header:{remaining}"));
    }
    let header = &bytes[offset..offset + HEADER_LEN];
    if &header[0..4] != MAGIC {
        return Err("bad_magic".to_owned());
    }
    if get_u16(header, 4) != VERSION {
        return Err("bad_version".to_owned());
    }
    if usize::from(get_u16(header, 6)) != HEADER_LEN {
        return Err("bad_header_length".to_owned());
    }
    if get_u64(header, 8) != GENERATION {
        return Err("wrong_generation".to_owned());
    }
    // Version 1 defines no flags and no reserved semantics, so a nonzero
    // value marks a frame this reader does not understand even when its
    // checksum verifies. Accepting it would replay an unknown format.
    if get_u32(header, FLAGS_OFFSET) != 0 {
        return Err("nonzero_flags".to_owned());
    }
    if get_u32(header, RESERVED_OFFSET) != 0 {
        return Err("nonzero_reserved".to_owned());
    }
    let lsn = get_u64(header, 16);
    if lsn != expected_lsn {
        return Err(format!("non_contiguous_lsn:{lsn}:expected:{expected_lsn}"));
    }
    let payload_len = get_u32(header, 24) as usize;
    if payload_len > MAX_PAYLOAD {
        return Err(format!("payload_too_large:{payload_len}"));
    }
    let total = HEADER_LEN
        .checked_add(payload_len)
        .ok_or_else(|| "frame_length_overflow".to_owned())?;
    if remaining < total {
        return Err(format!("truncated_payload:{remaining}:need:{total}"));
    }
    let stored_checksum = get_u32(header, CHECKSUM_OFFSET);
    let mut canonical = bytes[offset..offset + total].to_vec();
    put_u32(&mut canonical, CHECKSUM_OFFSET, 0);
    let actual_checksum = crc32c(&canonical);
    if actual_checksum != stored_checksum {
        return Err(format!(
            "checksum_mismatch:{actual_checksum:08x}:stored:{stored_checksum:08x}"
        ));
    }
    Ok(offset + total)
}

/// Recovers the longest valid sequence of frames starting at LSN 1.
///
/// An invalid suffix is a recoverable tail only when every LSN through
/// `required_lsn` is valid. This distinction models the commit boundary: a
/// damaged uncommitted tail can be discarded, while damaged acknowledged
/// history fails closed.
///
/// # Errors
///
/// Returns an error when fewer than `required_lsn` contiguous records survive
/// framing, sequence, length, generation, flags, reserved-field, and checksum
/// validation.
///
/// # Examples
///
/// ```
/// use wal_crash_consistency::{encode_frame, recover_prefix};
///
/// let first = encode_frame(1, b"one")?;
/// let mut torn_tail = first.clone();
/// torn_tail.extend_from_slice(&encode_frame(2, b"two")?[..12]);
/// let recovered = recover_prefix(&torn_tail, 1)?;
/// assert_eq!(recovered.valid_bytes(), first.len());
/// assert_eq!(recovered.tail_reason(), Some("truncated_header:12"));
/// # Ok::<(), wal_crash_consistency::WalError>(())
/// ```
pub fn recover_prefix(bytes: &[u8], required_lsn: u64) -> Result<Recovery, WalError> {
    let mut offset = 0_usize;
    let mut next_lsn = 1_u64;
    let mut tail_reason = None;
    while offset < bytes.len() {
        match inspect_frame(bytes, offset, next_lsn) {
            Ok(next) => {
                offset = next;
                next_lsn = next_lsn
                    .checked_add(1)
                    .ok_or_else(|| WalError("lsn_overflow".to_owned()))?;
            }
            Err(reason) => {
                tail_reason = Some(reason);
                break;
            }
        }
    }
    let valid_lsn = next_lsn - 1;
    if valid_lsn < required_lsn {
        return Err(WalError(format!(
            "required_history_damaged:required_lsn={required_lsn}:valid_lsn={valid_lsn}:tail={}",
            tail_reason.as_deref().unwrap_or("clean_end")
        )));
    }
    Ok(Recovery {
        valid_lsn,
        valid_bytes: offset,
        tail_reason,
        semantic_crc32c: crc32c(&bytes[..offset]),
    })
}

/// Executes the deterministic byte-state oracle and returns its stable receipt.
///
/// The oracle enumerates every prefix cut and every single-bit flip in a
/// three-frame log. It also checks committed-versus-uncommitted corruption,
/// sequence gaps, and recovery idempotence.
///
/// # Errors
///
/// Returns the first violated oracle as a [`WalError`].
pub fn verify_model() -> Result<String, WalError> {
    let f1 = encode_frame(1, b"alpha")?;
    let f2 = encode_frame(2, b"bravo-bravo")?;
    let f3 = encode_frame(3, b"charlie-charlie-charlie")?;
    let mut log = Vec::new();
    log.extend_from_slice(&f1);
    let boundary1 = log.len();
    log.extend_from_slice(&f2);
    let boundary2 = log.len();
    log.extend_from_slice(&f3);
    let boundary3 = log.len();

    let full = recover_prefix(&log, 3)?;
    if full.valid_lsn != 3 || full.valid_bytes != log.len() || full.tail_reason.is_some() {
        return Err(WalError(format!("full_log_oracle_failed:{full:?}")));
    }

    for cut in 0..=log.len() {
        let expected =
            u64::from(cut >= boundary1) + u64::from(cut >= boundary2) + u64::from(cut >= boundary3);
        let recovered = recover_prefix(&log[..cut], 0)?;
        if recovered.valid_lsn != expected {
            return Err(WalError(format!(
                "prefix_cut_oracle_failed:cut={cut}:expected={expected}:actual={}",
                recovered.valid_lsn
            )));
        }
    }

    for byte_index in 0..log.len() {
        let mut damaged = log.clone();
        damaged[byte_index] ^= 1;
        if recover_prefix(&damaged, 3).is_ok() {
            return Err(WalError(format!(
                "single_bit_fault_was_accepted:byte={byte_index}"
            )));
        }
    }

    let mut corrupt_tail = log.clone();
    corrupt_tail[boundary2 + HEADER_LEN] ^= 1;
    let allowed = recover_prefix(&corrupt_tail, 2)?;
    if allowed.valid_lsn != 2 || allowed.tail_reason.is_none() {
        return Err(WalError(format!(
            "uncommitted_tail_oracle_failed:{allowed:?}"
        )));
    }
    if recover_prefix(&corrupt_tail, 3).is_ok() {
        return Err(WalError(
            "committed_corruption_did_not_fail_closed".to_owned(),
        ));
    }

    let mut gap = Vec::new();
    gap.extend_from_slice(&f1);
    gap.extend_from_slice(&f2);
    gap.extend_from_slice(&encode_frame(9, b"gap")?);
    let gap_recovery = recover_prefix(&gap, 2)?;
    if gap_recovery.valid_lsn != 2
        || !gap_recovery
            .tail_reason()
            .unwrap_or("")
            .starts_with("non_contiguous_lsn")
    {
        return Err(WalError(format!("sequence_oracle_failed:{gap_recovery:?}")));
    }

    let valid_prefix = &corrupt_tail[..allowed.valid_bytes];
    let second_recovery = recover_prefix(valid_prefix, 2)?;
    if second_recovery.valid_lsn != allowed.valid_lsn
        || second_recovery.semantic_crc32c != allowed.semantic_crc32c
    {
        return Err(WalError(format!(
            "recovery_idempotence_failed:first={allowed:?}:second={second_recovery:?}"
        )));
    }

    Ok(format!(
        "MODEL,status=pass,frames=3,prefix_cuts={},single_bit_faults={},committed_corruption=fail_closed,uncommitted_tail=truncate_to_lsn_2,sequence_gap=reject,idempotent_digest={:08x}\nMODEL_SCOPE,process_crash=not_modeled_here,power_loss=byte_state_model_only,physical_power_cut=not_tested,storage_flush_contract=not_tested",
        log.len() + 1,
        log.len(),
        second_recovery.semantic_crc32c
    ))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crc32c_matches_standard_check_value() {
        assert_eq!(crc32c(b"123456789"), 0xe306_9283);
    }

    #[test]
    fn deterministic_model_covers_prefixes_and_corruption() -> Result<(), WalError> {
        let receipt = verify_model()?;
        assert!(receipt.starts_with("MODEL,status=pass,frames=3,prefix_cuts="));
        assert!(receipt.contains("committed_corruption=fail_closed"));
        Ok(())
    }

    #[test]
    fn required_history_distinguishes_committed_from_tail_damage() -> Result<(), WalError> {
        let first = encode_frame(1, b"one")?;
        let second = encode_frame(2, b"two")?;
        let mut log = first.clone();
        log.extend_from_slice(&second);
        log[first.len() + HEADER_LEN] ^= 1;

        let allowed = recover_prefix(&log, 1)?;
        assert_eq!(allowed.valid_bytes(), first.len());
        assert!(recover_prefix(&log, 2).is_err());
        Ok(())
    }

    #[test]
    fn payload_limit_is_checked_without_allocating() {
        let payload = vec![0_u8; MAX_PAYLOAD + 1];
        assert_eq!(
            encode_frame(1, &payload).unwrap_err().to_string(),
            format!("payload_too_large:{}:maximum:{MAX_PAYLOAD}", payload.len())
        );
    }

    #[test]
    fn nonzero_flags_and_reserved_fail_even_with_valid_checksum() -> Result<(), WalError> {
        for (offset, reason) in [
            (FLAGS_OFFSET, "nonzero_flags"),
            (RESERVED_OFFSET, "nonzero_reserved"),
        ] {
            let mut frame = encode_frame(1, b"one")?;
            put_u32(&mut frame, offset, 1);
            put_u32(&mut frame, CHECKSUM_OFFSET, 0);
            let checksum = crc32c(&frame);
            put_u32(&mut frame, CHECKSUM_OFFSET, checksum);

            assert!(recover_prefix(&frame, 1).is_err());
            let tail = recover_prefix(&frame, 0)?;
            assert_eq!(tail.valid_lsn(), 0);
            assert_eq!(tail.tail_reason(), Some(reason));
        }
        Ok(())
    }
}
