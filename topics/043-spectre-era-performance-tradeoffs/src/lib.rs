//! Small, inspectable shapes for comparing a branch, bounds masking, and a
//! speculation barrier.
//!
//! The three lookup functions have the same architectural result: a valid
//! index returns its word and an invalid index returns zero. Their generated
//! code differs on supported Linux targets. [`topic43_mask_lookup`] uses an
//! unsigned compare and a data-dependent mask. [`topic43_barrier_lookup`]
//! places an architecture barrier after the bounds check. These functions are
//! experiment subjects, not a complete Spectre defense or a security proof.
//!
//! Run `cargo run --release --package spectre-era-performance-tradeoffs --bin
//! spectre-tradeoff-probe -- --mode mask --iterations 1000000` for one fresh
//! process measurement.

#[cfg(not(any(
    all(target_os = "linux", target_arch = "x86_64"),
    all(target_os = "linux", target_arch = "aarch64")
)))]
use std::sync::atomic::{Ordering, compiler_fence};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Lookup shape selected by the experiment process.
pub enum LookupMode {
    /// Bounds-check branch with no experiment-specific mitigation.
    Plain,
    /// Bounds-check result carried into the address through an integer mask.
    Mask,
    /// Bounds-check branch followed by an architecture speculation barrier.
    Barrier,
}
#[must_use]
/// Returns the selected lookup shape's stable command-line name.
pub const fn mode_name(mode: LookupMode) -> &'static str {
    match mode {
        LookupMode::Plain => "plain",
        LookupMode::Mask => "mask",
        LookupMode::Barrier => "barrier",
    }
}

#[unsafe(no_mangle)]
#[inline(never)]
#[must_use]
/// Performs a checked lookup with no experiment-specific speculation control.
///
/// The exact symbol name lets the host harness disassemble this function
/// without depending on Rust's mangling scheme. Returning zero for an invalid
/// index matches the other two experiment shapes.
///
/// # Examples
///
/// ```
/// use spectre_era_performance_tradeoffs::topic43_plain_lookup;
///
/// assert_eq!(topic43_plain_lookup(&[7, 11], 1), 11);
/// assert_eq!(topic43_plain_lookup(&[7, 11], 3), 0);
/// ```
pub fn topic43_plain_lookup(words: &[u64], index: usize) -> u64 {
    words.get(index).copied().unwrap_or(0)
}

#[unsafe(no_mangle)]
#[inline(never)]
#[must_use]
/// Performs a checked lookup through an architecture-specific unsigned mask.
///
/// Linux x86-64 emits `cmp` plus `sbb`. Linux AArch64 emits `cmp`, `sbc`, and
/// Consumption of Speculative Data Barrier (`CSDB`). Other build targets use a
/// portable arithmetic fallback so developers can run correctness tests; that
/// fallback has no documented speculation-control contract.
///
/// # Examples
///
/// ```
/// use spectre_era_performance_tradeoffs::topic43_mask_lookup;
///
/// assert_eq!(topic43_mask_lookup(&[7, 11], 1), 11);
/// assert_eq!(topic43_mask_lookup(&[7, 11], usize::MAX), 0);
/// ```
pub fn topic43_mask_lookup(words: &[u64], index: usize) -> u64 {
    if words.is_empty() {
        return 0;
    }

    let len = words.len();
    #[cfg(all(target_os = "linux", target_arch = "x86_64"))]
    let mask = {
        let mask: usize;
        // SAFETY: The assembly reads two integer registers, writes one integer
        // register, and touches neither memory nor the stack.
        unsafe {
            core::arch::asm!(
                "cmp {index}, {len}",
                "sbb {mask}, {mask}",
                index = in(reg) index,
                len = in(reg) len,
                mask = lateout(reg) mask,
                options(nomem, nostack),
            );
        }
        mask
    };
    #[cfg(all(target_os = "linux", target_arch = "aarch64"))]
    let mask = {
        let mask: usize;
        // SAFETY: The assembly reads two integer registers, writes one integer
        // register, and touches neither memory nor the stack. `CSDB` completes
        // the architecture's conditional data-dependency sequence.
        unsafe {
            core::arch::asm!(
                "cmp {index}, {len}",
                "sbc {mask}, xzr, xzr",
                "csdb",
                index = in(reg) index,
                len = in(reg) len,
                mask = lateout(reg) mask,
                options(nomem, nostack),
            );
        }
        mask
    };
    #[cfg(not(any(
        all(target_os = "linux", target_arch = "x86_64"),
        all(target_os = "linux", target_arch = "aarch64")
    )))]
    let mask = 0_usize.wrapping_sub(usize::from(index < len));

    let safe_index = index & mask;
    // On the measured 64-bit targets the index mask already spans the word, so
    // the cast preserves the assembly's data dependency unchanged.
    #[cfg(any(
        all(target_os = "linux", target_arch = "x86_64"),
        all(target_os = "linux", target_arch = "aarch64")
    ))]
    let word_mask = mask as u64;
    // The correctness-only fallback re-derives an all-ones u64: widening a
    // 32-bit usize mask would clear the upper half of every valid word.
    #[cfg(not(any(
        all(target_os = "linux", target_arch = "x86_64"),
        all(target_os = "linux", target_arch = "aarch64")
    )))]
    let word_mask = 0_u64.wrapping_sub(u64::from(index < len));
    words[safe_index] & word_mask
}

#[inline(always)]
fn speculation_barrier_impl() {
    #[cfg(all(target_os = "linux", target_arch = "x86_64"))]
    // SAFETY: `lfence` has no operands and does not access the stack. Omitting
    // `nomem` keeps the inline-assembly block as a compiler memory barrier.
    unsafe {
        core::arch::asm!("lfence", options(nostack, preserves_flags));
    }

    #[cfg(all(target_os = "linux", target_arch = "aarch64"))]
    // SAFETY: Both barriers have no operands and do not access the stack.
    // Omitting `nomem` prevents compiler motion of memory operations across it.
    unsafe {
        core::arch::asm!("dsb nsh", "isb", options(nostack, preserves_flags));
    }

    #[cfg(not(any(
        all(target_os = "linux", target_arch = "x86_64"),
        all(target_os = "linux", target_arch = "aarch64")
    )))]
    compiler_fence(Ordering::SeqCst);
}

#[unsafe(no_mangle)]
#[inline(never)]
/// Prevents later experiment work from crossing this point on supported Linux.
///
/// Linux x86-64 emits `lfence`. Linux AArch64 uses the architecture-approved
/// fallback sequence `dsb nsh; isb`, where Data Synchronization Barrier (`DSB`)
/// waits for the non-shareable domain and Instruction Synchronization Barrier
/// (`ISB`) flushes the following instruction stream. Other targets receive a
/// compiler fence only and cannot supply barrier evidence for this topic.
/// The lookup benchmark inlines the same private implementation so its timed
/// path does not include a helper call and return.
///
/// # Examples
///
/// ```
/// use spectre_era_performance_tradeoffs::topic43_speculation_barrier;
///
/// topic43_speculation_barrier();
/// ```
pub fn topic43_speculation_barrier() {
    speculation_barrier_impl();
}

#[unsafe(no_mangle)]
#[inline(never)]
#[must_use]
/// Performs a checked lookup after a target-specific speculation barrier.
///
/// The branch rejects an invalid index before the barrier. This placement is
/// part of the generated-code inspection gate.
///
/// # Examples
///
/// ```
/// use spectre_era_performance_tradeoffs::topic43_barrier_lookup;
///
/// assert_eq!(topic43_barrier_lookup(&[7, 11], 1), 11);
/// assert_eq!(topic43_barrier_lookup(&[7, 11], 3), 0);
/// ```
pub fn topic43_barrier_lookup(words: &[u64], index: usize) -> u64 {
    if index >= words.len() {
        return 0;
    }
    speculation_barrier_impl();
    words[index]
}

#[inline(never)]
#[must_use]
/// Performs one lookup using `mode`.
///
/// # Examples
///
/// ```
/// use spectre_era_performance_tradeoffs::{LookupMode, lookup};
///
/// assert_eq!(lookup(LookupMode::Mask, &[3, 5], 0), 3);
/// ```
pub fn lookup(mode: LookupMode, words: &[u64], index: usize) -> u64 {
    match mode {
        LookupMode::Plain => topic43_plain_lookup(words, index),
        LookupMode::Mask => topic43_mask_lookup(words, index),
        LookupMode::Barrier => topic43_barrier_lookup(words, index),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn modes_match_on_boundary_cases() {
        let words = [3, 5, 8, 13];
        let indices = [0, 1, 3, 4, usize::MAX];
        for index in indices {
            let expected = topic43_plain_lookup(&words, index);
            assert_eq!(topic43_mask_lookup(&words, index), expected);
            assert_eq!(topic43_barrier_lookup(&words, index), expected);
        }
    }

    #[test]
    fn modes_preserve_words_wider_than_u32() {
        // A 32-bit index mask widened to u64 would clear the upper word half.
        let words = [0x1_0000_0000, u64::MAX, 0xdead_beef_0000_0001];
        for index in [0, 1, 2, 3, usize::MAX] {
            let expected = topic43_plain_lookup(&words, index);
            assert_eq!(topic43_mask_lookup(&words, index), expected);
            assert_eq!(topic43_barrier_lookup(&words, index), expected);
        }
    }

    #[test]
    fn modes_match_for_empty_input() {
        for mode in [LookupMode::Plain, LookupMode::Mask, LookupMode::Barrier] {
            assert_eq!(lookup(mode, &[], 0), 0);
            assert_eq!(lookup(mode, &[], usize::MAX), 0);
        }
    }

    #[test]
    fn fixed_stream_has_one_checksum() {
        let words: Vec<u64> = (0_u64..257).map(|word| word.wrapping_mul(17)).collect();
        let indices: Vec<usize> = (0_usize..1024)
            .map(|step| step.wrapping_mul(0x9e37_79b1) & 511)
            .collect();
        let checksums: Vec<u64> = [LookupMode::Plain, LookupMode::Mask, LookupMode::Barrier]
            .map(|mode| {
                indices.iter().fold(0_u64, |sum, &index| {
                    sum.wrapping_add(lookup(mode, &words, index))
                })
            })
            .into();
        assert_eq!(checksums[0], checksums[1]);
        assert_eq!(checksums[1], checksums[2]);
    }
}
