//! Controlled branch-versus-select kernels for x86-64 and AArch64.
//!
//! [`forced_branch_sum`] and [`forced_select_sum`] share inputs, iteration
//! order, constants, and wrapping arithmetic. On x86-64 and AArch64, inline
//! assembly fixes each data-dependent choice as either a conditional branch or
//! a register select. The compiler still controls loop branches, register
//! allocation, and surrounding code, so a timing comparison requires
//! inspection of the linked binary.
//!
//! [`hinted_pick`] shows the portable Rust API. Its source-level hint does not
//! promise a machine instruction.
//!
//! # Example
//!
//! ```
//! use systems_snackpack_topic_007::{forced_branch_sum, forced_select_sum};
//!
//! let conditions = [0, 1, 0, 1];
//! assert_eq!(forced_branch_sum(&conditions, 3), 60);
//! assert_eq!(forced_select_sum(&conditions, 3), 60);
//! ```

#![deny(missing_docs)]
#![deny(rustdoc::broken_intra_doc_links)]

/// Value selected by a zero condition.
pub const FALSE_VALUE: u64 = 3;

/// Value selected by a nonzero condition.
pub const TRUE_VALUE: u64 = 7;

/// Reports whether the build target supports the experiment's fixed machine
/// instruction shapes.
///
/// x86-64 uses `test` plus `jz` or `cmovne`. AArch64 uses `cbz` or `cmp` plus
/// `csel`. Other targets retain equivalent Rust fallbacks for correctness but
/// cannot support the controlled timing comparison.
pub const fn forced_code_shape_supported() -> bool {
    cfg!(any(target_arch = "x86_64", target_arch = "aarch64"))
}

/// Selects the true or false value through Rust's unpredictability hint.
///
/// The hint is stable in the workspace's Rust 1.93 minimum version. It does
/// not guarantee branchless lowering and is not a constant-time primitive.
#[inline(never)]
pub fn hinted_pick(condition: u8) -> u64 {
    std::hint::select_unpredictable(condition != 0, TRUE_VALUE, FALSE_VALUE)
}

#[cfg(target_arch = "x86_64")]
#[inline(always)]
fn branch_pick(condition: u8) -> u64 {
    let mut value = FALSE_VALUE;
    let true_value = TRUE_VALUE;

    // SAFETY: The assembly reads initialized register inputs, writes only the
    // output register and flags, and neither accesses memory nor the stack.
    unsafe {
        core::arch::asm!(
            "test {condition}, {condition}",
            "jz 2f",
            "mov {value}, {true_value}",
            "2:",
            condition = in(reg_byte) condition,
            value = inout(reg) value,
            true_value = in(reg) true_value,
            options(nomem, nostack),
        );
    }

    value
}

#[cfg(target_arch = "x86_64")]
#[inline(always)]
fn select_pick(condition: u8) -> u64 {
    let mut value = FALSE_VALUE;
    let true_value = TRUE_VALUE;

    // SAFETY: The assembly reads initialized register inputs, writes only the
    // output register and flags, and neither accesses memory nor the stack.
    unsafe {
        core::arch::asm!(
            "test {condition}, {condition}",
            "cmovne {value}, {true_value}",
            condition = in(reg_byte) condition,
            value = inout(reg) value,
            true_value = in(reg) true_value,
            options(nomem, nostack),
        );
    }

    value
}

#[cfg(target_arch = "aarch64")]
#[inline(always)]
fn branch_pick(condition: u8) -> u64 {
    let mut value = FALSE_VALUE;
    let true_value = TRUE_VALUE;
    let condition = u32::from(condition);

    // SAFETY: The assembly reads initialized register inputs, writes only the
    // output register, and neither accesses memory nor the stack.
    unsafe {
        core::arch::asm!(
            "cbz {condition:w}, 2f",
            "mov {value}, {true_value}",
            "2:",
            condition = in(reg) condition,
            value = inout(reg) value,
            true_value = in(reg) true_value,
            options(nomem, nostack),
        );
    }

    value
}

#[cfg(target_arch = "aarch64")]
#[inline(always)]
fn select_pick(condition: u8) -> u64 {
    let mut value = FALSE_VALUE;
    let true_value = TRUE_VALUE;
    let condition = u32::from(condition);

    // SAFETY: The assembly reads initialized register inputs, writes only the
    // output register and flags, and neither accesses memory nor the stack.
    unsafe {
        core::arch::asm!(
            "cmp {condition:w}, #0",
            "csel {value}, {true_value}, {value}, ne",
            condition = in(reg) condition,
            value = inout(reg) value,
            true_value = in(reg) true_value,
            options(nomem, nostack),
        );
    }

    value
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
#[inline(always)]
fn branch_pick(condition: u8) -> u64 {
    if condition == 0 {
        FALSE_VALUE
    } else {
        TRUE_VALUE
    }
}

#[cfg(not(any(target_arch = "x86_64", target_arch = "aarch64")))]
#[inline(always)]
fn select_pick(condition: u8) -> u64 {
    std::hint::select_unpredictable(condition != 0, TRUE_VALUE, FALSE_VALUE)
}

/// Sums fixed values through a forced data-dependent branch on supported targets.
///
/// Each nonzero byte selects [`TRUE_VALUE`]. Each zero byte selects
/// [`FALSE_VALUE`]. The function scans the complete slice `repetitions` times
/// and uses wrapping addition so the result is defined for every input size.
/// Other targets use an unconstrained Rust `if` for correctness only.
#[inline(never)]
pub fn forced_branch_sum(conditions: &[u8], repetitions: u64) -> u64 {
    let mut sum = 0_u64;
    for _ in 0..repetitions {
        for &condition in conditions {
            sum = sum.wrapping_add(branch_pick(condition));
        }
    }
    sum
}

/// Sums fixed values through a forced register select on supported targets.
///
/// The input contract and wrapping result match [`forced_branch_sum`]. On
/// supported targets, the tested choice changes from control flow to data flow.
/// Other targets use an unconstrained Rust selection for correctness only.
#[inline(never)]
pub fn forced_select_sum(conditions: &[u8], repetitions: u64) -> u64 {
    let mut sum = 0_u64;
    for _ in 0..repetitions {
        for &condition in conditions {
            sum = sum.wrapping_add(select_pick(condition));
        }
    }
    sum
}

/// Computes the reference sum modulo 2^64 without constraining machine code shape.
pub fn expected_sum(conditions: &[u8], repetitions: u64) -> u64 {
    let one_scan = conditions.iter().fold(0_u64, |sum, &condition| {
        let value = if condition == 0 {
            FALSE_VALUE
        } else {
            TRUE_VALUE
        };
        sum.wrapping_add(value)
    });
    one_scan.wrapping_mul(repetitions)
}

#[cfg(test)]
mod tests {
    use super::{
        FALSE_VALUE, TRUE_VALUE, expected_sum, forced_branch_sum, forced_select_sum, hinted_pick,
    };

    #[test]
    fn variants_match_for_binary_and_nonbinary_conditions() {
        let cases: &[&[u8]] = &[&[], &[0], &[1], &[0, 1, 0, 1], &[0, 2, 255, 0, 17]];

        for conditions in cases {
            for repetitions in [0, 1, 7, 31] {
                let expected = expected_sum(conditions, repetitions);
                assert_eq!(forced_branch_sum(conditions, repetitions), expected);
                assert_eq!(forced_select_sum(conditions, repetitions), expected);
            }
        }
    }

    #[test]
    fn hinted_selection_matches_the_value_contract() {
        assert_eq!(hinted_pick(0), FALSE_VALUE);
        assert_eq!(hinted_pick(1), TRUE_VALUE);
        assert_eq!(hinted_pick(255), TRUE_VALUE);
    }
}
