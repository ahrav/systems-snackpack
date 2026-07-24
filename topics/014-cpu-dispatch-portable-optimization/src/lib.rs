//! Runtime CPU dispatch that separates feature legality from selection policy.
//!
//! [`count_eq_scalar`] is the semantic oracle. [`resolve_best`] checks runtime
//! features before constructing [`ResolvedKernel`]. Its private function
//! pointer prevents safe callers from manufacturing an unchecked
//! specialization. The process-global [`resolve_cached`] result is valid for
//! the AVX2 and AArch64 Advanced SIMD contracts implemented here. A
//! fixed-vector-length Scalable Vector Extension (SVE) contract would require
//! per-thread validation.
//!
//! Selection proves that a kernel is executable in the current process. It does
//! not predict which kernel is profitable for an input.
//!
//! # Example
//!
//! ```
//! use systems_snackpack_topic_014::{count_eq_scalar, resolve_best};
//!
//! let input = b"dispatch";
//! let expected = count_eq_scalar(input, b'i');
//! assert_eq!(resolve_best().count(input, b'i'), expected);
//! ```

use std::fmt;
use std::sync::OnceLock;

/// Default benchmark input length; `TOPIC14_BYTES` overrides ad hoc runs.
pub const RECORDED_INPUT_BYTES: usize = 64 * 1024 * 1024;

/// Default pass count; `TOPIC14_PASSES` overrides ad hoc runs.
pub const RECORDED_PASSES: usize = 8;

/// Default chunk width; `TOPIC14_CHUNK_BYTES` overrides ad hoc runs.
pub const RECORDED_CHUNK_BYTES: usize = 256;

/// Byte counted by the recorded benchmark fixture.
pub const RECORDED_NEEDLE: u8 = 0x5a;

/// Implementation selected for one invocation boundary.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum KernelKind {
    /// Portable scalar oracle.
    Scalar,
    /// x86-64 AVX2 implementation.
    #[cfg(target_arch = "x86_64")]
    Avx2,
    /// AArch64 Advanced SIMD implementation.
    #[cfg(target_arch = "aarch64")]
    Neon,
}

impl KernelKind {
    /// Stable label used in process-level measurement records.
    #[must_use]
    pub const fn as_str(self) -> &'static str {
        match self {
            Self::Scalar => "scalar",
            #[cfg(target_arch = "x86_64")]
            Self::Avx2 => "avx2",
            #[cfg(target_arch = "aarch64")]
            Self::Neon => "neon",
        }
    }
}

type CountKernel = fn(&[u8], u8) -> usize;

/// A callable kernel paired with the feature proof used to construct it.
///
/// The function pointer is private so safe code cannot manufacture a SIMD
/// kernel without first passing the matching runtime feature check.
#[derive(Clone, Copy)]
pub struct ResolvedKernel {
    kind: KernelKind,
    function: CountKernel,
}

impl ResolvedKernel {
    /// Returns the implementation selected by runtime detection.
    #[must_use]
    pub const fn kind(self) -> KernelKind {
        self.kind
    }

    /// Counts `needle` using this resolved implementation.
    #[must_use]
    pub fn count(self, input: &[u8], needle: u8) -> usize {
        (self.function)(input, needle)
    }
}

impl fmt::Debug for ResolvedKernel {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter
            .debug_struct("ResolvedKernel")
            .field("kind", &self.kind)
            .finish_non_exhaustive()
    }
}

/// Error returned when a chunked call cannot make progress.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ZeroChunkSize;

impl fmt::Display for ZeroChunkSize {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        formatter.write_str("chunk size must be nonzero")
    }
}

impl std::error::Error for ZeroChunkSize {}

/// Counts bytes equal to `needle` without requesting optional ISA features.
///
/// This is the semantic oracle for every architecture-specific implementation.
/// The experiment disables LLVM's loop and superword-level parallelism
/// vectorizers when compiling its benchmark binary so this function remains a
/// scalar measurement control.
#[inline(never)]
#[must_use]
pub fn count_eq_scalar(input: &[u8], needle: u8) -> usize {
    let mut count = 0_usize;
    for &byte in input {
        count += usize::from(byte == needle);
    }
    count
}

#[cfg(target_arch = "x86_64")]
mod x86_64 {
    use core::arch::x86_64::{
        __m256i, _mm256_cmpeq_epi8, _mm256_loadu_si256, _mm256_movemask_epi8, _mm256_set1_epi8,
    };

    use super::count_eq_scalar;

    /// Counts matching bytes with AVX2 and handles the scalar tail.
    ///
    /// # Safety
    ///
    /// The current CPU and operating-system context must support AVX2. Callers
    /// can establish that precondition with
    /// [`std::arch::is_x86_feature_detected!("avx2")`].
    #[target_feature(enable = "avx2")]
    #[inline(never)]
    pub(super) unsafe fn count_eq_avx2_unchecked(input: &[u8], needle: u8) -> usize {
        const LANES: usize = 32;
        let mut offset = 0_usize;
        let mut count = 0_usize;
        let needle_vector = _mm256_set1_epi8(needle as i8);

        while offset + LANES <= input.len() {
            // The loop bound proves that all 32 bytes are within the slice.
            let bytes = unsafe { _mm256_loadu_si256(input.as_ptr().add(offset).cast::<__m256i>()) };
            let matches = _mm256_cmpeq_epi8(bytes, needle_vector);
            count += (_mm256_movemask_epi8(matches) as u32).count_ones() as usize;
            offset += LANES;
        }
        count + count_eq_scalar(&input[offset..], needle)
    }

    #[inline(never)]
    pub(super) fn count_eq_avx2_proven(input: &[u8], needle: u8) -> usize {
        // Only `resolve_best` and the checked entry point expose this thunk,
        // after runtime detection has established the target-feature contract.
        unsafe { count_eq_avx2_unchecked(input, needle) }
    }
}

#[cfg(target_arch = "aarch64")]
mod aarch64 {
    use core::arch::aarch64::{vaddvq_u8, vceqq_u8, vdupq_n_u8, vld1q_u8, vshrq_n_u8};

    use super::count_eq_scalar;

    /// Counts matching bytes with Advanced SIMD and handles the scalar tail.
    ///
    /// # Safety
    ///
    /// The current CPU and operating-system context must support `neon`.
    /// Callers can establish that precondition with
    /// [`std::arch::is_aarch64_feature_detected!("neon")`].
    #[target_feature(enable = "neon")]
    #[inline(never)]
    pub(super) unsafe fn count_eq_neon_unchecked(input: &[u8], needle: u8) -> usize {
        const LANES: usize = 16;
        let mut offset = 0_usize;
        let mut count = 0_usize;
        let needle_vector = vdupq_n_u8(needle);

        while offset + LANES <= input.len() {
            // The loop bound proves that all 16 bytes are within the slice.
            let bytes = unsafe { vld1q_u8(input.as_ptr().add(offset)) };
            let matches = vceqq_u8(bytes, needle_vector);
            let ones = vshrq_n_u8::<7>(matches);
            count += vaddvq_u8(ones) as usize;
            offset += LANES;
        }
        count + count_eq_scalar(&input[offset..], needle)
    }

    #[inline(never)]
    pub(super) fn count_eq_neon_proven(input: &[u8], needle: u8) -> usize {
        // Only `resolve_best` and the checked entry point expose this thunk,
        // after runtime detection has established the target-feature contract.
        unsafe { count_eq_neon_unchecked(input, needle) }
    }
}

/// Uses AVX2 when it is legal in the current x86-64 process.
///
/// `None` means that the complete AVX2 runtime feature contract was not
/// established. An empty input still performs the feature check.
#[cfg(target_arch = "x86_64")]
#[must_use]
pub fn count_eq_avx2_checked(input: &[u8], needle: u8) -> Option<usize> {
    std::arch::is_x86_feature_detected!("avx2").then(|| x86_64::count_eq_avx2_proven(input, needle))
}

/// Uses Advanced SIMD when it is legal in the current AArch64 process.
///
/// `None` means that the runtime feature contract was not established. An
/// empty input still performs the feature check.
#[cfg(target_arch = "aarch64")]
#[must_use]
pub fn count_eq_neon_checked(input: &[u8], needle: u8) -> Option<usize> {
    std::arch::is_aarch64_feature_detected!("neon")
        .then(|| aarch64::count_eq_neon_proven(input, needle))
}

/// Resolves the best implementation represented by this crate.
///
/// The ordering is a policy choice, not a speed measurement. Each SIMD choice
/// is guarded by the runtime feature check required by its unsafe callee.
#[must_use]
pub fn resolve_best() -> ResolvedKernel {
    #[cfg(target_arch = "x86_64")]
    if std::arch::is_x86_feature_detected!("avx2") {
        return ResolvedKernel {
            kind: KernelKind::Avx2,
            function: x86_64::count_eq_avx2_proven,
        };
    }

    #[cfg(target_arch = "aarch64")]
    if std::arch::is_aarch64_feature_detected!("neon") {
        return ResolvedKernel {
            kind: KernelKind::Neon,
            function: aarch64::count_eq_neon_proven,
        };
    }

    ResolvedKernel {
        kind: KernelKind::Scalar,
        function: count_eq_scalar,
    }
}

/// Returns a process-global resolved kernel.
///
/// This cache is valid for the implemented AVX2 and Advanced SIMD contracts.
/// It must not be copied unchanged to a feature whose legality varies by
/// thread, such as a fixed AArch64 Scalable Vector Extension vector-length
/// requirement.
#[must_use]
pub fn resolve_cached() -> &'static ResolvedKernel {
    static KERNEL: OnceLock<ResolvedKernel> = OnceLock::new();
    KERNEL.get_or_init(resolve_best)
}

/// Resolves once for the complete input and invokes the selected kernel.
#[inline(never)]
#[must_use]
pub fn count_eq_dispatch_once(input: &[u8], needle: u8) -> usize {
    resolve_best().count(input, needle)
}

fn count_chunks_with(
    kernel: ResolvedKernel,
    input: &[u8],
    needle: u8,
    chunk_size: usize,
) -> Result<usize, ZeroChunkSize> {
    if chunk_size == 0 {
        return Err(ZeroChunkSize);
    }
    Ok(input
        .chunks(chunk_size)
        .map(|chunk| kernel.count(chunk, needle))
        .sum())
}

/// Resolves once, then invokes the selected function pointer for every chunk.
///
/// # Errors
///
/// Returns [`ZeroChunkSize`] when `chunk_size` is zero.
#[inline(never)]
pub fn count_eq_cached_chunks(
    input: &[u8],
    needle: u8,
    chunk_size: usize,
) -> Result<usize, ZeroChunkSize> {
    count_chunks_with(*resolve_cached(), input, needle, chunk_size)
}

/// Repeats runtime selection and invokes the result for every chunk.
///
/// The architecture detection implementation may cache raw feature discovery;
/// this function still pays the selection branches and resolver construction at
/// each chunk boundary.
///
/// # Errors
///
/// Returns [`ZeroChunkSize`] when `chunk_size` is zero.
#[inline(never)]
pub fn count_eq_detect_chunks(
    input: &[u8],
    needle: u8,
    chunk_size: usize,
) -> Result<usize, ZeroChunkSize> {
    if chunk_size == 0 {
        return Err(ZeroChunkSize);
    }
    Ok(input
        .chunks(chunk_size)
        .map(|chunk| resolve_best().count(chunk, needle))
        .sum())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture(length: usize) -> Vec<u8> {
        (0..length)
            .map(|index| {
                let mixed = (index as u64)
                    .wrapping_mul(0x9e37_79b9_7f4a_7c15)
                    .rotate_left(17)
                    ^ 0xd1b5_4a32_d192_ed03;
                (mixed >> 56) as u8
            })
            .collect()
    }

    fn assert_all_paths(length: usize, needle: u8) {
        let input = fixture(length);
        let expected = count_eq_scalar(&input, needle);
        assert_eq!(resolve_best().count(&input, needle), expected);
        assert_eq!(resolve_cached().count(&input, needle), expected);
        assert_eq!(count_eq_dispatch_once(&input, needle), expected);
        for chunk_size in [1, 3, 15, 16, 17, 31, 32, 33, 255, 256, 257] {
            assert_eq!(
                count_eq_cached_chunks(&input, needle, chunk_size),
                Ok(expected)
            );
            assert_eq!(
                count_eq_detect_chunks(&input, needle, chunk_size),
                Ok(expected)
            );
        }

        #[cfg(target_arch = "x86_64")]
        if std::arch::is_x86_feature_detected!("avx2") {
            assert_eq!(count_eq_avx2_checked(&input, needle), Some(expected));
        }

        #[cfg(target_arch = "aarch64")]
        if std::arch::is_aarch64_feature_detected!("neon") {
            assert_eq!(count_eq_neon_checked(&input, needle), Some(expected));
        }
    }

    #[test]
    fn variants_match_scalar_at_vector_and_chunk_boundaries() {
        for length in [
            0, 1, 15, 16, 17, 31, 32, 33, 63, 64, 65, 255, 256, 257, 1023,
        ] {
            assert_all_paths(length, 0x5a);
            assert_all_paths(length, 0xff);
        }
    }

    #[test]
    fn zero_chunk_size_is_rejected() {
        assert_eq!(count_eq_cached_chunks(&[1, 2, 3], 1, 0), Err(ZeroChunkSize));
        assert_eq!(count_eq_detect_chunks(&[1, 2, 3], 1, 0), Err(ZeroChunkSize));
    }
}
