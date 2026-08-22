//! Small, executable contracts for Rust aliasing and pointer provenance.
//!
//! A reference is more than an address. `&mut T` grants exclusive access for
//! the reference's live use, while `&T` grants shared read access. Raw pointers
//! can express overlap, but the caller must uphold validity and lifetime rules.
//! Pointer provenance is abstract permission information that constrains which
//! memory a pointer may access, when, and whether it may write.
//!
//! [`strict_provenance_write`] changes an element by moving an address within
//! one live array while preserving the original pointer's provenance.
//! [`exposed_address_compares_equal`] performs an exposed-address round trip
//! only for comparison; it never dereferences the reconstructed pointer.
//! [`topic42_reference_contract`] and [`topic42_raw_contract`] make the
//! optimization difference between disjoint references and possibly aliasing
//! raw pointers visible. Run `cargo run --package rust-aliasing-provenance
//! --example provenance_demo` for the deterministic example.

use std::mem::size_of;

/// The observable result of one load-store-load contract.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct ContractOutcome {
    /// Sum of the source observations before and after the store.
    pub returned: u64,
    /// Destination value after the intervening store.
    pub destination: u64,
    /// Source value after the contract; exact raw overlap changes it.
    pub source: u64,
}

/// Writes `99` to the third array element through a Strict Provenance pointer
/// and returns the array.
///
/// `pointer::with_addr` copies `base`'s provenance to the computed address; it
/// does not prove that the address is in bounds. The fixed displacement names
/// `words[2]` while the array remains live and exclusively owned.
#[must_use]
pub fn strict_provenance_write() -> [u64; 4] {
    let mut words = [10_u64, 20, 30, 40];
    let base = words.as_mut_ptr();
    let third_address = base.addr() + 2 * size_of::<u64>();
    let third = base.with_addr(third_address);

    // SAFETY: `third_address` is the address of `words[2]`. `with_addr` keeps
    // `base`'s provenance, the array is alive, and this function owns the
    // array exclusively for the write.
    unsafe {
        third.write(99);
    }
    words
}

/// Compares a pointer with an exposed-provenance reconstruction by address.
///
/// Exposed Provenance uses a conceptual global set to reconstruct a pointer
/// from an integer address. Unlike `with_addr`, the reconstruction does not
/// identify which exposed provenance the implementation selects. This function
/// reconstructs the address for comparison only; it neither dereferences the
/// pointer nor treats equal addresses as proof of a valid access.
#[must_use]
pub fn exposed_address_compares_equal() -> bool {
    let word = 7_u64;
    let original = &raw const word;
    let exposed_address = original.expose_provenance();
    let reconstructed = std::ptr::with_exposed_provenance::<u64>(exposed_address);
    reconstructed.addr() == original.addr()
}

/// Runs the reference contract with source `7` and a distinct destination.
#[must_use]
pub fn reference_example() -> ContractOutcome {
    let mut destination = 100_u64;
    let source = 7_u64;
    let returned = topic42_reference_contract(&mut destination, &source);
    ContractOutcome {
        returned,
        destination,
        source,
    }
}

/// Runs the raw-pointer contract with source `7` and a distinct destination.
#[must_use]
pub fn raw_distinct_example() -> ContractOutcome {
    let mut destination = 100_u64;
    let source = 7_u64;
    // SAFETY: both pointers refer to live, aligned, initialized `u64` objects.
    // The destination is writable, the source is readable, and they are
    // distinct for the duration of the call.
    let returned = unsafe { topic42_raw_contract(&raw mut destination, &raw const source) };
    ContractOutcome {
        returned,
        destination,
        source,
    }
}

/// Runs the raw-pointer contract with both arguments targeting one `u64`
/// initialized to `7`.
#[must_use]
pub fn raw_alias_example() -> ContractOutcome {
    let mut value = 7_u64;
    let pointer = &raw mut value;
    // SAFETY: `pointer` refers to one live, aligned, initialized, writable
    // `u64`. Exact overlap is allowed by `topic42_raw_contract`'s contract,
    // and no reference accesses `value` during the call.
    let returned = unsafe { topic42_raw_contract(pointer, pointer.cast_const()) };
    ContractOutcome {
        returned,
        destination: value,
        source: value,
    }
}

/// Returns twice the source value while storing source plus one in a disjoint
/// destination.
///
/// A valid call cannot make `destination` overlap `source`. The retained
/// optimized LLVM output marks both parameters `noalias` and contains one
/// source load; other compiler versions or options need not use that lowering.
/// The exported, non-inlined symbol has Rust's application binary interface
/// (ABI) and exists only for generated-code inspection.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic42_reference_contract(destination: &mut u64, source: &u64) -> u64 {
    let first = *source;
    *destination = first.wrapping_add(1);
    first.wrapping_add(*source)
}

/// Returns the sum of the source values observed before and after the
/// destination store.
///
/// Unlike [`topic42_reference_contract`], this contract explicitly permits
/// `destination` and `source` to be the same `u64`. The second load must then
/// observe the intervening store. The exported, non-inlined C-compatible
/// symbol exists for LLVM intermediate-representation and native-code
/// inspection.
///
/// # Safety
///
/// Supply non-null, properly aligned pointers whose provenance covers one live
/// `u64` for the whole call. Make `destination` writable and make `source`
/// readable and initialized. The pointees may be exactly the same object.
/// Prevent other accesses that conflict with either pointer's reads or writes,
/// including unsynchronized cross-thread access and access through references
/// whose contracts would be violated.
#[unsafe(no_mangle)]
#[inline(never)]
pub unsafe extern "C" fn topic42_raw_contract(destination: *mut u64, source: *const u64) -> u64 {
    // SAFETY: the caller supplies the validity, access, provenance, and race
    // guarantees above. The contract permits exact overlap, so the second
    // source read intentionally occurs after the destination write.
    unsafe {
        let first = source.read();
        destination.write(first.wrapping_add(1));
        first.wrapping_add(source.read())
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn strict_provenance_write_stays_within_the_array() {
        assert_eq!(strict_provenance_write(), [10, 20, 99, 40]);
    }

    #[test]
    fn exposed_address_is_compared_without_being_dereferenced() {
        assert!(exposed_address_compares_equal());
    }

    #[test]
    fn distinct_reference_and_raw_calls_agree() {
        let expected = ContractOutcome {
            returned: 14,
            destination: 8,
            source: 7,
        };
        assert_eq!(reference_example(), expected);
        assert_eq!(raw_distinct_example(), expected);
    }

    #[test]
    fn permitted_raw_alias_observes_the_intervening_store() {
        assert_eq!(
            raw_alias_example(),
            ContractOutcome {
                returned: 15,
                destination: 8,
                source: 8,
            }
        );
    }
}
