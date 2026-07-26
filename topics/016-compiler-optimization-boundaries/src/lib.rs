//! Small kernels for observing a cross-crate compiler optimization boundary.
//!
//! [`imported_inline_mix`] publishes an inlineable body to downstream crates.
//! [`topic16_opaque_mix`] remains an ordinary separately compiled call when
//! link-time optimization is disabled. The checked-in experiment establishes
//! the actual result from the final linked image rather than treating either
//! attribute as a guarantee.

/// Mixes one word while publishing its body in crate metadata.
///
/// `#[inline(always)]` requests downstream inlining; only the final linked
/// image establishes whether a particular caller contains the body.
#[inline(always)]
pub fn imported_inline_mix(x: u32, salt: u32) -> u32 {
    let y = x ^ salt;
    y.rotate_left(5).wrapping_add(y ^ 0x9e37_79b9)
}

/// Mixes one word behind a separately compiled, externally named boundary.
///
/// The stable symbol name supports final-image inspection. Neither the C ABI
/// nor the exported name guarantees that an optimizer retains a call.
#[unsafe(no_mangle)]
pub extern "C" fn topic16_opaque_mix(x: u32, salt: u32) -> u32 {
    let y = x ^ salt;
    y.rotate_left(5).wrapping_add(y ^ 0x9e37_79b9)
}

#[cfg(test)]
mod tests {
    use super::{imported_inline_mix, topic16_opaque_mix};

    #[test]
    fn visible_and_opaque_forms_agree() {
        let cases = [
            (0, 0),
            (1, 2),
            (u32::MAX, 0x9e37_79b9),
            (0xdead_beef, 0x1234_5678),
        ];

        for (word, salt) in cases {
            assert_eq!(
                imported_inline_mix(word, salt),
                topic16_opaque_mix(word, salt)
            );
        }
    }
}
