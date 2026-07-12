//! Compares compiler-visible CRC32-C intrinsics with inline assembly.
//!
//! The fold keeps four independent CRC states and XORs them at the end. It
//! measures code generation around the update instruction; it does not encode a
//! standard CRC32-C file format. AArch64 uses the CRC extension after runtime
//! detection. Other targets use the reference update routine.
//!
//! # Examples
//!
//! ```
//! use systems_snackpack_topic_002::{fold_inline_asm, fold_intrinsic};
//!
//! let words = [1_u64, 2, 3, 4, 5];
//! assert_eq!(fold_intrinsic(&words), fold_inline_asm(&words));
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

const CRC32C_POLYNOMIAL: u32 = 0x82f6_3b78;

/// Folds words through four portable CRC32-C reference states.
///
/// Each word updates the state selected by its index modulo four. The function
/// XORs the four final states. It provides the semantic oracle for the AArch64
/// implementations in this crate.
pub fn fold_reference(words: &[u64]) -> u32 {
    let mut lanes = [0_u32, 1, 2, 3];
    for (index, word) in words.iter().enumerate() {
        lanes[index % lanes.len()] = crc32c_update_word(lanes[index % lanes.len()], *word);
    }
    lanes
        .into_iter()
        .reduce(|left, right| left ^ right)
        .unwrap_or(0)
}

/// Folds words with the AArch64 CRC32-C intrinsic when the CPU supports it.
///
/// Other targets, or AArch64 CPUs without the CRC extension, use
/// [`fold_reference`].
pub fn fold_intrinsic(words: &[u64]) -> u32 {
    #[cfg(target_arch = "aarch64")]
    {
        if std::arch::is_aarch64_feature_detected!("crc") {
            // SAFETY: runtime detection proves that the CRC extension can execute.
            return unsafe { fold_intrinsic_impl(words) };
        }
    }

    fold_reference(words)
}

/// Folds words with AArch64 inline assembly when the CPU supports CRC32-C.
///
/// Other targets, or AArch64 CPUs without the CRC extension, use
/// [`fold_reference`].
pub fn fold_inline_asm(words: &[u64]) -> u32 {
    #[cfg(target_arch = "aarch64")]
    {
        if std::arch::is_aarch64_feature_detected!("crc") {
            // SAFETY: runtime detection proves that the CRC instruction can execute.
            return unsafe { fold_inline_asm_impl(words) };
        }
    }

    fold_reference(words)
}

fn crc32c_update_word(mut crc: u32, word: u64) -> u32 {
    for byte in word.to_le_bytes() {
        crc ^= u32::from(byte);
        for _ in 0..8 {
            let mask = 0_u32.wrapping_sub(crc & 1);
            crc = (crc >> 1) ^ (CRC32C_POLYNOMIAL & mask);
        }
    }
    crc
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "crc")]
unsafe fn fold_intrinsic_impl(words: &[u64]) -> u32 {
    use core::arch::aarch64::__crc32cd;

    let mut lanes = [0_u32, 1, 2, 3];
    let mut blocks = words.chunks_exact(4);
    for block in &mut blocks {
        lanes[0] = __crc32cd(lanes[0], block[0]);
        lanes[1] = __crc32cd(lanes[1], block[1]);
        lanes[2] = __crc32cd(lanes[2], block[2]);
        lanes[3] = __crc32cd(lanes[3], block[3]);
    }
    for (index, word) in blocks.remainder().iter().enumerate() {
        lanes[index] = __crc32cd(lanes[index], *word);
    }
    lanes
        .into_iter()
        .reduce(|left, right| left ^ right)
        .unwrap_or(0)
}

#[cfg(target_arch = "aarch64")]
#[target_feature(enable = "crc")]
unsafe fn fold_inline_asm_impl(words: &[u64]) -> u32 {
    use core::arch::asm;

    let mut lanes = [0_u32, 1, 2, 3];
    let mut blocks = words.chunks_exact(4);
    for block in &mut blocks {
        let (x0, x1, x2, x3) = (block[0], block[1], block[2], block[3]);
        unsafe {
            asm!(
                "crc32cx {a:w}, {a:w}, {x0:x}",
                "crc32cx {b:w}, {b:w}, {x1:x}",
                "crc32cx {c:w}, {c:w}, {x2:x}",
                "crc32cx {d:w}, {d:w}, {x3:x}",
                a = inout(reg) lanes[0], b = inout(reg) lanes[1],
                c = inout(reg) lanes[2], d = inout(reg) lanes[3],
                x0 = in(reg) x0, x1 = in(reg) x1,
                x2 = in(reg) x2, x3 = in(reg) x3,
                options(pure, nomem, nostack, preserves_flags),
            );
        }
    }
    for (index, word) in blocks.remainder().iter().enumerate() {
        lanes[index] = unsafe { crc32c_asm_word(lanes[index], *word) };
    }
    lanes
        .into_iter()
        .reduce(|left, right| left ^ right)
        .unwrap_or(0)
}

#[cfg(target_arch = "aarch64")]
/// Updates one CRC state with a register-only `crc32cx` instruction.
///
/// # Safety
///
/// The current CPU must support the AArch64 CRC extension.
#[target_feature(enable = "crc")]
unsafe fn crc32c_asm_word(mut crc: u32, word: u64) -> u32 {
    use core::arch::asm;

    unsafe {
        asm!(
            "crc32cx {crc:w}, {crc:w}, {word:x}",
            crc = inout(reg) crc,
            word = in(reg) word,
            options(pure, nomem, nostack, preserves_flags),
        );
    }
    crc
}

#[cfg(test)]
mod tests {
    use super::{fold_inline_asm, fold_intrinsic, fold_reference};

    #[test]
    fn public_paths_match_the_reference() {
        let words: Vec<u64> = (0..517)
            .map(|index| (index as u64).wrapping_mul(0x9e37_79b9_7f4a_7c15))
            .collect();
        let expected = fold_reference(&words);
        assert_eq!(fold_intrinsic(&words), expected);
        assert_eq!(fold_inline_asm(&words), expected);
    }

    #[test]
    fn empty_input_has_a_stable_fold() {
        assert_eq!(fold_reference(&[]), 0);
        assert_eq!(fold_intrinsic(&[]), 0);
        assert_eq!(fold_inline_asm(&[]), 0);
    }
}
