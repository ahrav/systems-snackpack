//! Unmangled symbol boundaries for inspecting Rust-to-ISA atomic lowering.
//!
//! Each unmangled wrapper contains one atomic or fence operation.
//! [`publication_roundtrip`] supplies a separate correctness example in which a
//! store with `Ordering::Release` publishes a payload store with
//! `Ordering::Relaxed` to a consumer load with `Ordering::Acquire`.
//!
//! # Evidence boundary
//!
//! Rust specifies ordering semantics, not instruction names. An instruction-level
//! observation applies only to the recorded rustc, LLVM, target, target features,
//! compiler flags, and final binary.
//!
//! # Example
//!
//! ```
//! assert_eq!(atomic_lowering::publication_roundtrip(10_000), 10_000);
//! ```

use std::hint::spin_loop;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering, compiler_fence, fence};
use std::thread;

/// Creates no cross-location synchronization edge by itself.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn load_relaxed(cell: &AtomicU64) -> u64 {
    cell.load(Ordering::Relaxed)
}

/// Makes accesses before a release operation happen before later accesses when
/// this load reads from that operation's release sequence.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn load_acquire(cell: &AtomicU64) -> u64 {
    cell.load(Ordering::Acquire)
}

/// Applies acquire semantics and joins the global order of `Ordering::SeqCst`
/// operations.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn load_seqcst(cell: &AtomicU64) -> u64 {
    cell.load(Ordering::SeqCst)
}

/// Publishes no preceding accesses to other locations by itself.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn store_relaxed(cell: &AtomicU64, value: u64) {
    cell.store(value, Ordering::Relaxed);
}

/// Makes preceding accesses happen before accesses after an acquire operation
/// that reads from this store's release sequence.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn store_release(cell: &AtomicU64, value: u64) {
    cell.store(value, Ordering::Release);
}

/// Applies release semantics and joins the global order of `Ordering::SeqCst`
/// operations.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn store_seqcst(cell: &AtomicU64, value: u64) {
    cell.store(value, Ordering::SeqCst);
}

/// Returns the value preceding a wrapping addition; neither half orders accesses
/// to other locations.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fetch_add_relaxed(cell: &AtomicU64, value: u64) -> u64 {
    cell.fetch_add(value, Ordering::Relaxed)
}

/// Returns the value preceding a wrapping addition; `Ordering::Acquire` applies
/// only to the load half, leaving the store half `Ordering::Relaxed`.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fetch_add_acquire(cell: &AtomicU64, value: u64) -> u64 {
    cell.fetch_add(value, Ordering::Acquire)
}

/// Returns the value preceding a wrapping addition; `Ordering::Release` applies
/// only to the store half, leaving the load half `Ordering::Relaxed`.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fetch_add_release(cell: &AtomicU64, value: u64) -> u64 {
    cell.fetch_add(value, Ordering::Release)
}

/// Returns the value preceding a wrapping addition; `Ordering::Acquire` applies
/// to the load half and `Ordering::Release` applies to the store half.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fetch_add_acqrel(cell: &AtomicU64, value: u64) -> u64 {
    cell.fetch_add(value, Ordering::AcqRel)
}

/// Returns the value preceding a wrapping addition, applies acquire and release
/// semantics, and joins the global order of `Ordering::SeqCst` operations.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fetch_add_seqcst(cell: &AtomicU64, value: u64) -> u64 {
    cell.fetch_add(value, Ordering::SeqCst)
}

/// Pairs a preceding atomic read with a release operation whose release sequence
/// it reads from; accesses after the fence then happen after that operation.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fence_acquire() {
    fence(Ordering::Acquire);
}

/// Pairs a following atomic write with an acquire operation that reads from it;
/// accesses before the fence then happen before that acquire operation.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fence_release() {
    fence(Ordering::Release);
}

/// Applies acquire fence semantics to preceding atomic reads and release fence
/// semantics to following atomic writes.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fence_acqrel() {
    fence(Ordering::AcqRel);
}

/// Applies acquire and release fence semantics and joins the global order of
/// `Ordering::SeqCst` operations and fences.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn fence_seqcst() {
    fence(Ordering::SeqCst);
}

/// Restricts compiler reordering without emitting machine code and can synchronize
/// only with code that runs on the same hardware CPU.
#[unsafe(no_mangle)]
#[inline(never)]
pub extern "C" fn compiler_fence_seqcst() {
    compiler_fence(Ordering::SeqCst);
}

/// Transfers each payload through a release/acquire epoch and returns the value
/// consumed in the final epoch.
///
/// The payload uses `Ordering::Relaxed` atomic accesses. The consumer may rely on
/// the value only after its `Ordering::Acquire` load reads the producer's released
/// epoch. The acknowledgement prevents the producer from replacing that payload
/// before the consumer reads it.
///
/// # Panics
///
/// - If `rounds` is zero.
/// - If the operating system cannot spawn the producer thread.
/// - If the payload read after an acquired epoch differs from that epoch.
///
/// # Examples
///
/// ```
/// assert_eq!(atomic_lowering::publication_roundtrip(10_000), 10_000);
/// ```
pub fn publication_roundtrip(rounds: u64) -> u64 {
    assert!(rounds > 0, "rounds must be nonzero");
    let payload = AtomicU64::new(0);
    let published = AtomicU64::new(0);
    let consumed = AtomicU64::new(0);
    let abort = AtomicBool::new(false);

    thread::scope(|scope| {
        scope.spawn(|| {
            for value in 1..=rounds {
                loop {
                    // A consumer assertion failure unwinds the scope, which
                    // then joins this thread; without this check the producer
                    // would spin forever on an acknowledgement that never
                    // arrives and the process would hang instead of failing.
                    if abort.load(Ordering::Acquire) {
                        return;
                    }
                    if consumed.load(Ordering::Acquire) == value - 1 {
                        break;
                    }
                    spin_loop();
                }
                payload.store(value, Ordering::Relaxed);
                published.store(value, Ordering::Release);
            }
        });

        for expected in 1..=rounds {
            while published.load(Ordering::Acquire) != expected {
                spin_loop();
            }
            let observed = payload.load(Ordering::Relaxed);
            if observed != expected {
                abort.store(true, Ordering::Release);
                panic!("payload {observed} does not match acquired epoch {expected}");
            }
            consumed.store(expected, Ordering::Release);
        }
    });

    payload.load(Ordering::Relaxed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn release_acquire_publishes_payload() {
        assert_eq!(publication_roundtrip(100_000), 100_000);
    }

    #[test]
    #[should_panic(expected = "rounds must be nonzero")]
    fn zero_rounds_is_rejected() {
        publication_roundtrip(0);
    }
}
