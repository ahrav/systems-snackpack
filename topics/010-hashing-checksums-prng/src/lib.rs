//! Exact CRC parameter sets and a focused CRC32C dispatch experiment.
//!
//! The CRC32C implementations in this crate all use the Castagnoli parameter
//! set: width 32, normal polynomial `0x1EDC6F41`, reflected input and output,
//! initial state `0xFFFFFFFF`, and final XOR `0xFFFFFFFF`. The public update
//! functions accept and return finalized CRCs, so callers begin with zero and
//! may feed adjacent fragments in order without exposing the internal raw
//! state.
//!
//! ```
//! use systems_snackpack_topic_010::{Crc32cKernel, crc32c_bitwise};
//!
//! let table = Crc32cKernel::table();
//! let first = table.update(0, b"1234");
//! let fragmented = table.update(first, b"56789");
//! assert_eq!(fragmented, 0xe306_9283);
//! assert_eq!(fragmented, crc32c_bitwise(b"123456789"));
//!
//! if let Some(hardware) = Crc32cKernel::detect_hardware() {
//!     assert_eq!(hardware.checksum(b"123456789"), fragmented);
//! }
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

use std::fmt;

/// Normal-form polynomial for CRC32C (Castagnoli).
pub const CRC32C_NORMAL_POLYNOMIAL: u32 = 0x1edc_6f41;

/// Reflected polynomial used by right-shifting CRC32C implementations.
pub const CRC32C_REFLECTED_POLYNOMIAL: u32 = 0x82f6_3b78;

/// Normal-form polynomial for CRC-32/ISO-HDLC.
pub const CRC32_ISO_HDLC_NORMAL_POLYNOMIAL: u32 = 0x04c1_1db7;

/// Reflected polynomial used by right-shifting CRC-32/ISO-HDLC implementations.
pub const CRC32_ISO_HDLC_REFLECTED_POLYNOMIAL: u32 = 0xedb8_8320;

const CRC32C_TABLE: [u32; 256] = make_reflected_table(CRC32C_REFLECTED_POLYNOMIAL);

type UpdateFn = fn(u32, &[u8]) -> u32;

/// A CRC32C implementation selected before entering a measured loop.
///
/// [`Self::table`] is available on every target. [`Self::detect_hardware`]
/// returns a kernel only after runtime feature detection proves that the
/// current process may execute the target-specific instructions. Its fields
/// are private so safe callers cannot construct an unchecked hardware kernel.
#[derive(Clone, Copy)]
pub struct Crc32cKernel {
    name: &'static str,
    hardware: bool,
    update: UpdateFn,
}

impl Crc32cKernel {
    /// Returns the portable, 1-KiB slice-by-one table kernel.
    pub const fn table() -> Self {
        Self {
            name: "table",
            hardware: false,
            update: crc32c_table_update,
        }
    }

    /// Detects a dedicated-instruction CRC32C kernel at runtime.
    ///
    /// On x86-64 this requires SSE4.2 and uses the `CRC32` instruction. On
    /// AArch64 this requires FEAT_CRC32 and uses the `CRC32C*` instructions.
    /// Other targets return `None`.
    pub fn detect_hardware() -> Option<Self> {
        detect_hardware_update().map(|update| Self {
            name: "hardware",
            hardware: true,
            update,
        })
    }

    /// Returns the hardware kernel when available, otherwise the table kernel.
    pub fn best_available() -> Self {
        Self::detect_hardware().unwrap_or_else(Self::table)
    }

    /// Returns the stable experiment label for this kernel.
    pub const fn name(self) -> &'static str {
        self.name
    }

    /// Reports whether this kernel uses target-specific CRC instructions.
    pub const fn is_hardware(self) -> bool {
        self.hardware
    }

    /// Extends a finalized CRC32C with the next adjacent byte slice.
    ///
    /// Use zero as the CRC for the first fragment. The returned value can be
    /// passed back as `previous` for the next adjacent fragment.
    pub fn update(self, previous: u32, bytes: &[u8]) -> u32 {
        (self.update)(previous, bytes)
    }

    /// Computes a finalized CRC32C over one byte slice.
    pub fn checksum(self, bytes: &[u8]) -> u32 {
        self.update(0, bytes)
    }
}

impl fmt::Debug for Crc32cKernel {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("Crc32cKernel")
            .field("name", &self.name)
            .field("hardware", &self.hardware)
            .finish_non_exhaustive()
    }
}

/// Computes CRC32C with an independent bit-at-a-time reference algorithm.
///
/// This implementation is intentionally slow and structurally independent of
/// [`crc32c_table_update`]. It is the differential oracle for this artifact.
pub fn crc32c_bitwise(bytes: &[u8]) -> u32 {
    crc32c_bitwise_update(0, bytes)
}

/// Extends a finalized CRC32C with a bit-at-a-time reference algorithm.
///
/// Use zero for the first fragment. Pass each returned CRC back as `previous`
/// when processing the next adjacent fragment.
pub fn crc32c_bitwise_update(previous: u32, bytes: &[u8]) -> u32 {
    reflected_bitwise_update(previous, bytes, CRC32C_REFLECTED_POLYNOMIAL)
}

/// Computes CRC-32/ISO-HDLC with a bit-at-a-time reference algorithm.
///
/// This uses the Ethernet/zlib polynomial rather than Castagnoli. The
/// dedicated x86 SSE4.2 `CRC32` instruction does not compute this value.
pub fn crc32_iso_hdlc_bitwise(bytes: &[u8]) -> u32 {
    reflected_bitwise_update(0, bytes, CRC32_ISO_HDLC_REFLECTED_POLYNOMIAL)
}

/// Extends a finalized CRC32C with the portable slice-by-one table kernel.
///
/// The exported symbol name provides a stable boundary for linked-binary
/// disassembly in the focused experiment.
#[inline(never)]
// SAFETY: this crate defines this topic-prefixed symbol exactly once. The
// target-specific hardware definitions use a different name, so the export
// cannot collide within a linked Topic 10 benchmark.
#[unsafe(export_name = "topic010_crc32c_table_update")]
pub fn crc32c_table_update(previous: u32, bytes: &[u8]) -> u32 {
    let mut state = !previous;
    for &byte in bytes {
        let index = usize::from((state as u8) ^ byte);
        state = CRC32C_TABLE[index] ^ (state >> 8);
    }
    !state
}

/// Computes a finalized CRC32C with the portable slice-by-one table kernel.
pub fn crc32c_table(bytes: &[u8]) -> u32 {
    crc32c_table_update(0, bytes)
}

const fn make_reflected_table(polynomial: u32) -> [u32; 256] {
    let mut table = [0_u32; 256];
    let mut index = 0;
    while index < table.len() {
        let mut value = index as u32;
        let mut bit = 0;
        while bit < 8 {
            value = if value & 1 == 0 {
                value >> 1
            } else {
                (value >> 1) ^ polynomial
            };
            bit += 1;
        }
        table[index] = value;
        index += 1;
    }
    table
}

fn reflected_bitwise_update(previous: u32, bytes: &[u8], polynomial: u32) -> u32 {
    let mut state = !previous;
    for &byte in bytes {
        state ^= u32::from(byte);
        for _ in 0..8 {
            let mask = 0_u32.wrapping_sub(state & 1);
            state = (state >> 1) ^ (polynomial & mask);
        }
    }
    !state
}

#[cfg(target_arch = "x86_64")]
fn detect_hardware_update() -> Option<UpdateFn> {
    std::arch::is_x86_feature_detected!("sse4.2").then_some(x86_hardware_dispatch)
}

#[cfg(target_arch = "x86_64")]
fn x86_hardware_dispatch(previous: u32, bytes: &[u8]) -> u32 {
    // SAFETY: this function pointer is installed only after the runtime
    // detector above confirms SSE4.2 support. `bytes` remains a valid slice;
    // the target-feature leaf performs only checked slice reads.
    unsafe { crc32c_hardware_update(previous, bytes) }
}

#[cfg(target_arch = "x86_64")]
#[target_feature(enable = "sse4.2")]
#[inline(never)]
// SAFETY: only this x86-64 definition is compiled on this target. The AArch64
// definition is cfg-exclusive, and the topic-prefixed name is unique within
// the linked benchmark.
#[unsafe(export_name = "topic010_crc32c_hardware_update")]
unsafe fn crc32c_hardware_update(previous: u32, bytes: &[u8]) -> u32 {
    use std::arch::x86_64::{_mm_crc32_u8, _mm_crc32_u16, _mm_crc32_u32, _mm_crc32_u64};

    let mut state = u64::from(!previous);
    let mut chunks = bytes.chunks_exact(8);
    for chunk in &mut chunks {
        let word = u64::from_le_bytes(chunk.try_into().expect("chunk is exactly eight bytes"));
        state = _mm_crc32_u64(state, word);
    }

    let mut tail = chunks.remainder();
    if tail.len() >= 4 {
        let word = u32::from_le_bytes(tail[..4].try_into().expect("tail has four bytes"));
        state = u64::from(_mm_crc32_u32(state as u32, word));
        tail = &tail[4..];
    }
    if tail.len() >= 2 {
        let word = u16::from_le_bytes(tail[..2].try_into().expect("tail has two bytes"));
        state = u64::from(_mm_crc32_u16(state as u32, word));
        tail = &tail[2..];
    }
    if let Some(&byte) = tail.first() {
        state = u64::from(_mm_crc32_u8(state as u32, byte));
    }
    !(state as u32)
}

#[cfg(target_arch = "aarch64")]
fn detect_hardware_update() -> Option<UpdateFn> {
    std::arch::is_aarch64_feature_detected!("crc").then_some(aarch64_hardware_dispatch)
}

#[cfg(target_arch = "aarch64")]
fn aarch64_hardware_dispatch(previous: u32, bytes: &[u8]) -> u32 {
    // SAFETY: this function pointer is installed only after the runtime
    // detector above confirms FEAT_CRC32 support. `bytes` remains a valid
    // slice; the target-feature leaf performs only checked slice reads.
    unsafe { crc32c_hardware_update(previous, bytes) }
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "crc")]
#[inline(never)]
// SAFETY: only this AArch64 definition is compiled on this target. The x86-64
// definition is cfg-exclusive, and the topic-prefixed name is unique within
// the linked benchmark.
#[unsafe(export_name = "topic010_crc32c_hardware_update")]
unsafe fn crc32c_hardware_update(previous: u32, bytes: &[u8]) -> u32 {
    use std::arch::aarch64::{__crc32cb, __crc32cd, __crc32ch, __crc32cw};

    let mut state = !previous;
    let mut chunks = bytes.chunks_exact(8);
    for chunk in &mut chunks {
        let word = u64::from_le_bytes(chunk.try_into().expect("chunk is exactly eight bytes"));
        state = __crc32cd(state, word);
    }

    let mut tail = chunks.remainder();
    if tail.len() >= 4 {
        let word = u32::from_le_bytes(tail[..4].try_into().expect("tail has four bytes"));
        state = __crc32cw(state, word);
        tail = &tail[4..];
    }
    if tail.len() >= 2 {
        let word = u16::from_le_bytes(tail[..2].try_into().expect("tail has two bytes"));
        state = __crc32ch(state, word);
        tail = &tail[2..];
    }
    if let Some(&byte) = tail.first() {
        state = __crc32cb(state, byte);
    }
    !state
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
fn detect_hardware_update() -> Option<UpdateFn> {
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn standard_check_vectors_distinguish_the_polynomials() {
        assert_eq!(crc32c_bitwise(b"123456789"), 0xe306_9283);
        assert_eq!(crc32c_table(b"123456789"), 0xe306_9283);
        assert_eq!(crc32_iso_hdlc_bitwise(b"123456789"), 0xcbf4_3926);
        assert_ne!(
            crc32c_table(b"123456789"),
            crc32_iso_hdlc_bitwise(b"123456789")
        );
    }

    #[test]
    fn empty_and_fragmented_updates_match_the_oracle() {
        let data = deterministic_bytes(257);
        let expected = crc32c_bitwise(&data);
        let table = Crc32cKernel::table();
        assert_eq!(table.checksum(&[]), 0);

        for split in 0..=data.len() {
            let first = table.update(0, &data[..split]);
            assert_eq!(
                table.update(first, &data[split..]),
                expected,
                "split {split}"
            );
        }
    }

    #[test]
    fn every_short_length_and_offset_matches() {
        let data = deterministic_bytes(32 + 512);
        let hardware = Crc32cKernel::detect_hardware();
        for offset in 0..32 {
            for len in 0..=512 {
                let input = &data[offset..offset + len];
                let expected = crc32c_bitwise(input);
                assert_eq!(
                    crc32c_table(input),
                    expected,
                    "offset {offset} length {len}"
                );
                if let Some(kernel) = hardware {
                    assert_eq!(
                        kernel.checksum(input),
                        expected,
                        "hardware offset {offset} length {len}"
                    );
                }
            }
        }
    }

    #[test]
    fn kernel_metadata_matches_selection() {
        let table = Crc32cKernel::table();
        assert_eq!(table.name(), "table");
        assert!(!table.is_hardware());
        assert_eq!(
            Crc32cKernel::best_available().is_hardware(),
            Crc32cKernel::detect_hardware().is_some()
        );
    }

    fn deterministic_bytes(len: usize) -> Vec<u8> {
        let mut state = 0x243f_6a88_85a3_08d3_u64;
        (0..len)
            .map(|_| {
                state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
                let mut value = state;
                value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
                value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
                (value ^ (value >> 31)) as u8
            })
            .collect()
    }
}
