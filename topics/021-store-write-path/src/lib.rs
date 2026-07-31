//! Architecture-specific kernels for a publisher-shaped write path.
//!
//! The temporal and non-temporal kernels write the same complete cache-line
//! pattern and then publish a separate atomic flag with release ordering. The
//! x86-64 non-temporal path executes `SFENCE` before publication. The AArch64
//! path compares `STP` with the advisory `STNP` hint; publication uses the
//! architecture's release lowering.
//!
//! The store-to-load-forwarding (STLF) kernels hold a dependent recurrence in
//! a register. One load exactly covers the preceding store. The other begins
//! four bytes into it and also consumes four unchanged bytes beyond it.

use std::alloc::{Layout, alloc_zeroed, dealloc, handle_alloc_error};
use std::hint::black_box;
use std::ptr;
use std::sync::atomic::{AtomicU64, Ordering};

/// Required alignment for all experiment buffers.
pub const BUFFER_ALIGNMENT: usize = 4096;

/// Cache-line size assumed by the focused experiment.
pub const CACHE_LINE_BYTES: usize = 64;

/// Initial value carried by the dependent STLF recurrence.
pub const STLF_SEED: u64 = 0x9e37_79b9_7f4a_7c15;

const PATTERN_WORDS: [u64; 8] = [
    0x0123_4567_89ab_cdef,
    0xfedc_ba98_7654_3210,
    0x0f1e_2d3c_4b5a_6978,
    0x8877_6655_4433_2211,
    0x1357_9bdf_2468_ace0,
    0xc3d2_e1f0_a5b4_9687,
    0x55aa_33cc_f00f_9696,
    0xa1b2_c3d4_e5f6_0718,
];

/// Selects the cacheable or non-temporal write kernel.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum WriteMode {
    /// Cacheable vector stores.
    Temporal,
    /// x86-64 streaming stores or the AArch64 `STNP` hint.
    NonTemporal,
}

/// Selects the geometry of the dependent load after each store.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum StlfMode {
    /// The load exactly covers the preceding eight-byte store.
    Exact,
    /// The load begins four bytes into the preceding eight-byte store.
    Partial,
}

/// Result of checking every word written by a write kernel.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct Verification {
    /// Number of words that differ from the deterministic pattern.
    pub bad_words: usize,
    /// Order-sensitive digest over all observed words.
    pub digest: u64,
}

/// Page-aligned allocation used by the focused experiment.
pub struct AlignedBuffer {
    ptr: *mut u8,
    layout: Layout,
}

impl AlignedBuffer {
    /// Allocates a zero-initialized, nonempty whole-cache-line buffer.
    ///
    /// # Panics
    ///
    /// Panics when `size` is zero, is not a multiple of 64 bytes, or cannot
    /// be represented by an allocation layout. Allocation failure aborts
    /// through the standard allocation error handler.
    #[must_use]
    pub fn new(size: usize) -> Self {
        assert!(size > 0, "buffer size must be nonzero");
        assert_eq!(
            size % CACHE_LINE_BYTES,
            0,
            "buffer size must cover whole cache lines"
        );
        let layout = Layout::from_size_align(size, BUFFER_ALIGNMENT)
            .expect("buffer size and alignment must form a valid layout");
        // SAFETY: `layout` is nonzero and valid. Null is handled below.
        let ptr = unsafe { alloc_zeroed(layout) };
        if ptr.is_null() {
            handle_alloc_error(layout);
        }
        Self { ptr, layout }
    }

    /// Returns the allocation size in bytes.
    #[must_use]
    pub fn len(&self) -> usize {
        self.layout.size()
    }

    /// Reports whether the allocation is empty.
    #[must_use]
    pub fn is_empty(&self) -> bool {
        false
    }

    /// Returns the aligned allocation pointer.
    #[must_use]
    pub fn as_mut_ptr(&mut self) -> *mut u8 {
        self.ptr
    }

    /// Writes one byte value throughout the allocation.
    pub fn fill(&mut self, byte: u8) {
        // SAFETY: `ptr` owns `len` writable bytes for the lifetime of `self`.
        unsafe { ptr::write_bytes(self.ptr, byte, self.len()) };
    }

    /// Reads one word per cache line and returns an order-sensitive digest.
    ///
    /// This sweep is used outside the timed period to make the allocation
    /// resident and to displace the destination from private caches.
    #[must_use]
    pub fn sweep_lines(&self) -> u64 {
        let mut digest = 0xcbf2_9ce4_8422_2325_u64;
        for offset in (0..self.len()).step_by(CACHE_LINE_BYTES) {
            // SAFETY: every offset names an aligned word within the allocation.
            let word = unsafe { ptr::read_volatile(self.ptr.add(offset).cast::<u64>()) };
            digest = digest.rotate_left(7) ^ word.wrapping_add(offset as u64);
        }
        black_box(digest)
    }

    /// Checks every eight-byte word against the write-kernel pattern.
    #[must_use]
    pub fn verify_pattern(&self) -> Verification {
        let mut bad_words = 0_usize;
        let mut digest = 0xcbf2_9ce4_8422_2325_u64;
        for index in 0..(self.len() / 8) {
            // SAFETY: the page-aligned allocation contains this whole word.
            let value = unsafe { ptr::read_volatile(self.ptr.cast::<u64>().add(index)) };
            bad_words += usize::from(value != PATTERN_WORDS[index % PATTERN_WORDS.len()]);
            digest = digest.rotate_left(5) ^ value.wrapping_add(index as u64);
        }
        Verification { bad_words, digest }
    }

    /// Installs the deterministic 16-byte fixture used by the STLF oracle.
    pub fn initialize_stlf_fixture(&mut self) {
        for index in 0..16 {
            // SAFETY: all experiment allocations contain at least 64 bytes.
            unsafe {
                ptr::write(
                    self.ptr.add(index),
                    (index as u8).wrapping_mul(17).wrapping_add(3),
                );
            }
        }
    }
}

impl Drop for AlignedBuffer {
    fn drop(&mut self) {
        // SAFETY: the pointer was returned for this exact layout and has not
        // been deallocated yet.
        unsafe { dealloc(self.ptr, self.layout) };
    }
}

#[cfg(target_arch = "x86_64")]
mod arch {
    use super::{PATTERN_WORDS, StlfMode, WriteMode};
    use std::arch::asm;
    use std::arch::x86_64::{
        __m256i, _mm_sfence, _mm256_set_epi64x, _mm256_store_si256, _mm256_stream_si256,
    };
    use std::sync::atomic::{AtomicU64, Ordering};

    #[unsafe(no_mangle)]
    #[inline(never)]
    #[target_feature(enable = "avx2")]
    pub(super) unsafe fn topic21_temporal_store(
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        let first = _mm256_set_epi64x(
            PATTERN_WORDS[3] as i64,
            PATTERN_WORDS[2] as i64,
            PATTERN_WORDS[1] as i64,
            PATTERN_WORDS[0] as i64,
        );
        let second = _mm256_set_epi64x(
            PATTERN_WORDS[7] as i64,
            PATTERN_WORDS[6] as i64,
            PATTERN_WORDS[5] as i64,
            PATTERN_WORDS[4] as i64,
        );
        let mut offset = 0_usize;
        while offset < size {
            // SAFETY: the caller provides page alignment and a whole-line size.
            unsafe {
                _mm256_store_si256(dst.add(offset).cast::<__m256i>(), first);
                _mm256_store_si256(dst.add(offset + 32).cast::<__m256i>(), second);
            }
            offset += 64;
        }
        // SAFETY: `ready` points to a live atomic separate from `dst`.
        unsafe { (*ready).store(1, Ordering::Release) };
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    #[target_feature(enable = "avx2")]
    pub(super) unsafe fn topic21_nontemporal_store(
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        let first = _mm256_set_epi64x(
            PATTERN_WORDS[3] as i64,
            PATTERN_WORDS[2] as i64,
            PATTERN_WORDS[1] as i64,
            PATTERN_WORDS[0] as i64,
        );
        let second = _mm256_set_epi64x(
            PATTERN_WORDS[7] as i64,
            PATTERN_WORDS[6] as i64,
            PATTERN_WORDS[5] as i64,
            PATTERN_WORDS[4] as i64,
        );
        let mut offset = 0_usize;
        while offset < size {
            // SAFETY: the caller provides 32-byte alignment and full lines.
            unsafe {
                _mm256_stream_si256(dst.add(offset).cast::<__m256i>(), first);
                _mm256_stream_si256(dst.add(offset + 32).cast::<__m256i>(), second);
            }
            offset += 64;
        }
        _mm_sfence();
        // SAFETY: `ready` points to a live atomic separate from `dst`.
        unsafe { (*ready).store(1, Ordering::Release) };
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_stlf_exact(base: *mut u8, iterations: u64, seed: u64) -> u64 {
        let count = iterations;
        let mut value = seed;
        // SAFETY: the caller provides 16 initialized writable bytes. The loop
        // executes at least once, and the assembly touches only those bytes.
        unsafe {
            asm!(
                "2:",
                "mov qword ptr [{base}], {value}",
                "mov {value}, qword ptr [{base}]",
                "dec {count}",
                "jnz 2b",
                base = in(reg) base,
                value = inout(reg) value,
                count = inout(reg) count => _,
                options(nostack)
            );
        }
        value
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_stlf_partial(base: *mut u8, iterations: u64, seed: u64) -> u64 {
        let count = iterations;
        let mut value = seed;
        // SAFETY: the caller provides 16 initialized writable bytes. The loop
        // executes at least once, and the assembly touches only those bytes.
        unsafe {
            asm!(
                "2:",
                "mov qword ptr [{base}], {value}",
                "mov {value}, qword ptr [{base} + 4]",
                "dec {count}",
                "jnz 2b",
                base = in(reg) base,
                value = inout(reg) value,
                count = inout(reg) count => _,
                options(nostack)
            );
        }
        value
    }

    pub(super) fn supported() -> bool {
        std::arch::is_x86_feature_detected!("avx2")
    }

    pub(super) const NAME: &str = "x86_64";

    pub(super) unsafe fn write(
        mode: WriteMode,
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        match mode {
            WriteMode::Temporal => unsafe { topic21_temporal_store(dst, size, ready) },
            WriteMode::NonTemporal => unsafe { topic21_nontemporal_store(dst, size, ready) },
        }
    }

    pub(super) unsafe fn stlf(mode: StlfMode, base: *mut u8, iterations: u64, seed: u64) -> u64 {
        match mode {
            StlfMode::Exact => unsafe { topic21_stlf_exact(base, iterations, seed) },
            StlfMode::Partial => unsafe { topic21_stlf_partial(base, iterations, seed) },
        }
    }
}

#[cfg(target_arch = "aarch64")]
mod arch {
    use super::{PATTERN_WORDS, StlfMode, WriteMode};
    use std::arch::asm;
    use std::sync::atomic::{AtomicU64, Ordering};

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_temporal_store(
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        let mut offset = 0_usize;
        while offset < size {
            // SAFETY: the caller provides page alignment and a whole-line size.
            let address = unsafe { dst.add(offset) };
            // SAFETY: four pair stores cover exactly this initialized line.
            unsafe {
                asm!(
                    "stp {word0}, {word1}, [{address}, #0]",
                    "stp {word2}, {word3}, [{address}, #16]",
                    "stp {word4}, {word5}, [{address}, #32]",
                    "stp {word6}, {word7}, [{address}, #48]",
                    address = in(reg) address,
                    word0 = in(reg) PATTERN_WORDS[0],
                    word1 = in(reg) PATTERN_WORDS[1],
                    word2 = in(reg) PATTERN_WORDS[2],
                    word3 = in(reg) PATTERN_WORDS[3],
                    word4 = in(reg) PATTERN_WORDS[4],
                    word5 = in(reg) PATTERN_WORDS[5],
                    word6 = in(reg) PATTERN_WORDS[6],
                    word7 = in(reg) PATTERN_WORDS[7],
                    options(nostack, preserves_flags)
                );
            }
            offset += 64;
        }
        // SAFETY: `ready` points to a live atomic separate from `dst`.
        unsafe { (*ready).store(1, Ordering::Release) };
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_nontemporal_store(
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        let mut offset = 0_usize;
        while offset < size {
            // SAFETY: the caller provides page alignment and a whole-line size.
            let address = unsafe { dst.add(offset) };
            // SAFETY: four non-temporal pair-store hints cover this line.
            unsafe {
                asm!(
                    "stnp {word0}, {word1}, [{address}, #0]",
                    "stnp {word2}, {word3}, [{address}, #16]",
                    "stnp {word4}, {word5}, [{address}, #32]",
                    "stnp {word6}, {word7}, [{address}, #48]",
                    address = in(reg) address,
                    word0 = in(reg) PATTERN_WORDS[0],
                    word1 = in(reg) PATTERN_WORDS[1],
                    word2 = in(reg) PATTERN_WORDS[2],
                    word3 = in(reg) PATTERN_WORDS[3],
                    word4 = in(reg) PATTERN_WORDS[4],
                    word5 = in(reg) PATTERN_WORDS[5],
                    word6 = in(reg) PATTERN_WORDS[6],
                    word7 = in(reg) PATTERN_WORDS[7],
                    options(nostack, preserves_flags)
                );
            }
            offset += 64;
        }
        // SAFETY: `ready` points to a live atomic separate from `dst`. A
        // release store orders the earlier normal-memory pair stores before
        // the publication flag; `STNP` changes allocation policy, not type.
        unsafe { (*ready).store(1, Ordering::Release) };
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_stlf_exact(base: *mut u8, iterations: u64, seed: u64) -> u64 {
        let count = iterations;
        let mut value = seed;
        // SAFETY: the caller provides 16 initialized writable bytes. The loop
        // executes at least once, and the assembly touches only those bytes.
        unsafe {
            asm!(
                "2:",
                "str {value}, [{base}]",
                "ldur {value}, [{base}, #0]",
                "subs {count}, {count}, #1",
                "b.ne 2b",
                base = in(reg) base,
                value = inout(reg) value,
                count = inout(reg) count => _,
                options(nostack)
            );
        }
        value
    }

    #[unsafe(no_mangle)]
    #[inline(never)]
    pub(super) unsafe fn topic21_stlf_partial(base: *mut u8, iterations: u64, seed: u64) -> u64 {
        let count = iterations;
        let mut value = seed;
        // SAFETY: the caller provides 16 initialized writable bytes. The loop
        // executes at least once, and the assembly touches only those bytes.
        unsafe {
            asm!(
                "2:",
                "str {value}, [{base}]",
                "ldur {value}, [{base}, #4]",
                "subs {count}, {count}, #1",
                "b.ne 2b",
                base = in(reg) base,
                value = inout(reg) value,
                count = inout(reg) count => _,
                options(nostack)
            );
        }
        value
    }

    pub(super) fn supported() -> bool {
        cfg!(target_endian = "little")
    }

    pub(super) const NAME: &str = "aarch64";

    pub(super) unsafe fn write(
        mode: WriteMode,
        dst: *mut u8,
        size: usize,
        ready: *const AtomicU64,
    ) {
        match mode {
            WriteMode::Temporal => unsafe { topic21_temporal_store(dst, size, ready) },
            WriteMode::NonTemporal => unsafe { topic21_nontemporal_store(dst, size, ready) },
        }
    }

    pub(super) unsafe fn stlf(mode: StlfMode, base: *mut u8, iterations: u64, seed: u64) -> u64 {
        match mode {
            StlfMode::Exact => unsafe { topic21_stlf_exact(base, iterations, seed) },
            StlfMode::Partial => unsafe { topic21_stlf_partial(base, iterations, seed) },
        }
    }
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
compile_error!("Topic 21 supports only x86-64 and AArch64");

/// Returns the architecture name used in JSON records.
#[must_use]
pub fn architecture_name() -> &'static str {
    arch::NAME
}

/// Reports whether this process can execute both write kernels.
#[must_use]
pub fn write_kernels_supported() -> bool {
    arch::supported()
}

/// Writes the complete pattern and release-publishes `ready = 1`.
///
/// The destination must not be read or written concurrently. The wrapper
/// checks alignment, size, and target-feature support before entering the
/// architecture-specific kernel.
///
/// # Panics
///
/// Panics when the required target features are unavailable.
pub fn publish_pattern(mode: WriteMode, destination: &mut AlignedBuffer, ready: &AtomicU64) {
    assert!(
        write_kernels_supported(),
        "required write-kernel target features are unavailable"
    );
    ready.store(0, Ordering::Relaxed);
    // SAFETY: `AlignedBuffer` is page aligned, has a whole-line size, and is
    // exclusively accessed by the calling experiment. `ready` remains live.
    unsafe {
        arch::write(mode, destination.as_mut_ptr(), destination.len(), ready);
    }
}

/// Executes the dependent STLF recurrence over the initialized fixture.
///
/// # Panics
///
/// Panics when `iterations` is zero or this target is unsupported.
#[must_use]
pub fn run_stlf(mode: StlfMode, buffer: &mut AlignedBuffer, iterations: u64, seed: u64) -> u64 {
    assert!(iterations > 0, "STLF iterations must be nonzero");
    assert!(
        write_kernels_supported(),
        "required STLF target is unavailable"
    );
    // SAFETY: every `AlignedBuffer` contains at least one 64-byte line. The
    // fixture initializes the 16 bytes read or written by either geometry.
    unsafe { arch::stlf(mode, buffer.as_mut_ptr(), iterations, seed) }
}

/// Computes the deterministic STLF recurrence without inline assembly.
///
/// The partial-overlap recurrence becomes a fixed point after two updates, so
/// the oracle runs at most three state transitions even for long experiments.
#[must_use]
pub fn stlf_oracle(mode: StlfMode, iterations: u64, seed: u64) -> u64 {
    assert!(iterations > 0, "STLF iterations must be nonzero");
    let mut bytes = [0_u8; 16];
    for (index, byte) in bytes.iter_mut().enumerate() {
        *byte = (index as u8).wrapping_mul(17).wrapping_add(3);
    }
    let mut value = seed;
    let transitions = match mode {
        StlfMode::Exact => 1,
        StlfMode::Partial => iterations.min(3),
    };
    for _ in 0..transitions {
        bytes[..8].copy_from_slice(&value.to_ne_bytes());
        let offset = usize::from(mode == StlfMode::Partial) * 4;
        value = u64::from_ne_bytes(
            bytes[offset..offset + 8]
                .try_into()
                .expect("oracle slice has eight bytes"),
        );
    }
    value
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::atomic::{Ordering, fence};

    #[test]
    fn both_write_paths_publish_the_full_pattern() {
        if !write_kernels_supported() {
            return;
        }
        for mode in [WriteMode::Temporal, WriteMode::NonTemporal] {
            let mut destination = AlignedBuffer::new(64 * 1024);
            destination.fill(0xa5);
            let ready = AtomicU64::new(0);
            publish_pattern(mode, &mut destination, &ready);
            fence(Ordering::SeqCst);
            assert_eq!(ready.load(Ordering::Acquire), 1);
            assert_eq!(destination.verify_pattern().bad_words, 0);
        }
    }

    #[test]
    fn both_stlf_geometries_match_the_oracle() {
        if !write_kernels_supported() {
            return;
        }
        for mode in [StlfMode::Exact, StlfMode::Partial] {
            let mut buffer = AlignedBuffer::new(64);
            buffer.initialize_stlf_fixture();
            let observed = run_stlf(mode, &mut buffer, 4_096, STLF_SEED);
            assert_eq!(observed, stlf_oracle(mode, 4_096, STLF_SEED));
        }
    }
}
