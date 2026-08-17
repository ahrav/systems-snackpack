//! Checked models for Linux copy-avoidance decisions.
//!
//! “Zero-copy” means that one named payload copy is avoided. It does not mean
//! that bytes never move. Review a path by recording where bytes live, who owns
//! their storage, and which event makes that storage reusable.
//!
//! # Example
//!
//! ```
//! use zero_copy_limits::{
//!     FilePath, PathCostInputs, TransferCostInputs, compare_transfer_costs,
//!     file_path_accounting, held_bytes,
//! };
//!
//! let bytes = 64 * 1024 * 1024;
//! let buffered = file_path_accounting(FilePath::Buffered, bytes)?;
//! let sendfile = file_path_accounting(FilePath::Sendfile, bytes)?;
//! assert_eq!(buffered.named_payload_copy_bytes, 2 * bytes);
//! assert_eq!(sendfile.named_payload_copy_bytes, 0);
//!
//! let comparison = compare_transfer_costs(TransferCostInputs {
//!     baseline: PathCostInputs {
//!         logical_bytes: bytes,
//!         payload_copy_passes: 2,
//!         syscall_count: 128,
//!         copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
//!         fixed_syscall_ns: 200,
//!         other_ns: 0,
//!     },
//!     copy_avoiding: PathCostInputs {
//!         logical_bytes: bytes,
//!         payload_copy_passes: 0,
//!         syscall_count: 64,
//!         copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
//!         fixed_syscall_ns: 200,
//!         other_ns: 0,
//!     },
//! })?;
//! assert!(comparison.copy_avoiding_wins);
//!
//! // 20,000 sends/s * 64 KiB * 5 ms = 6.25 MiB retained on average.
//! assert_eq!(held_bytes(20_000, 64 * 1024, 5_000_000)?, 6_553_600);
//! # Ok::<(), zero_copy_limits::ModelError>(())
//! ```

use std::collections::BTreeSet;
use std::fmt;

const NANOS_PER_SECOND: u128 = 1_000_000_000;

/// A file-to-socket path used by the focused Linux experiment.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum FilePath {
    /// `pread` moves bytes into an application buffer, then `send` submits them.
    Buffered,
    /// `sendfile` asks the kernel to connect a file description to a socket.
    Sendfile,
    /// `splice` moves page references through a caller-visible pipe.
    Splice,
}

/// Checked payload-copy accounting at the application boundary.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct FilePathAccounting {
    /// Logical payload bytes delivered to the socket peer.
    pub logical_bytes: u64,
    /// Payload bytes copied on the named page-cache/application/socket path.
    ///
    /// This deliberately excludes device, protocol, checksum, encryption,
    /// storage, and receiver-side movement.
    pub named_payload_copy_bytes: u64,
    /// Whether the call directly exposes an application payload buffer.
    pub application_buffer_exposed: bool,
    /// Whether the path requires an explicit pipe in the caller.
    pub explicit_pipe: bool,
}

/// Invalid input or overflow in a checked model.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum ModelError {
    /// A page size was zero.
    ZeroPageSize,
    /// A modeled copy-bandwidth divisor was zero.
    ZeroCopyBandwidth,
    /// A pipe capacity was zero.
    ZeroPipeCapacity,
    /// A requested transfer chunk was zero.
    ZeroChunkSize,
    /// A wrapped identifier was reused while the old identifier remained outstanding.
    IdentifierStillOutstanding(u32),
    /// Integer arithmetic exceeded the selected representation.
    ArithmeticOverflow,
}

impl fmt::Display for ModelError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::ZeroPageSize => formatter.write_str("page size must be nonzero"),
            Self::ZeroCopyBandwidth => formatter.write_str("copy bandwidth must be nonzero"),
            Self::ZeroPipeCapacity => formatter.write_str("pipe capacity must be nonzero"),
            Self::ZeroChunkSize => formatter.write_str("requested chunk must be nonzero"),
            Self::IdentifierStillOutstanding(identifier) => {
                write!(formatter, "identifier {identifier} is still outstanding")
            }
            Self::ArithmeticOverflow => formatter.write_str("model arithmetic overflowed"),
        }
    }
}

impl std::error::Error for ModelError {}

/// Accounts for payload copies visible on the named file-to-socket path.
///
/// `Buffered` counts a page-cache-to-application copy and an
/// application-to-socket copy. `Sendfile` and `Splice` count neither because
/// their payload stays kernel-owned. A zero here is not a claim that no other
/// copy, direct-memory-access operation, checksum pass, or encryption pass
/// occurs.
///
/// # Errors
///
/// Returns [`ModelError::ArithmeticOverflow`] when twice `logical_bytes` does
/// not fit in `u64` for the buffered path.
pub fn file_path_accounting(
    path: FilePath,
    logical_bytes: u64,
) -> Result<FilePathAccounting, ModelError> {
    let named_payload_copy_bytes = match path {
        FilePath::Buffered => logical_bytes
            .checked_mul(2)
            .ok_or(ModelError::ArithmeticOverflow)?,
        FilePath::Sendfile | FilePath::Splice => 0,
    };
    Ok(FilePathAccounting {
        logical_bytes,
        named_payload_copy_bytes,
        application_buffer_exposed: path == FilePath::Buffered,
        explicit_pipe: path == FilePath::Splice,
    })
}

/// Returns the number of virtual-memory pages touched by a byte range.
///
/// The range is half-open: it begins at `offset` and contains `length` bytes.
/// A zero-length range touches no pages. This is an accounting upper boundary,
/// not proof that Linux pins, maps, or transmits that many physical pages.
///
/// # Errors
///
/// Returns [`ModelError::ZeroPageSize`] for a zero page size and
/// [`ModelError::ArithmeticOverflow`] when the range end cannot be represented.
///
/// # Examples
///
/// ```
/// use zero_copy_limits::pages_spanned;
///
/// assert_eq!(pages_spanned(0, 4096, 4096)?, 1);
/// assert_eq!(pages_spanned(4095, 2, 4096)?, 2);
/// # Ok::<(), zero_copy_limits::ModelError>(())
/// ```
pub fn pages_spanned(offset: u64, length: u64, page_size: u64) -> Result<u64, ModelError> {
    if page_size == 0 {
        return Err(ModelError::ZeroPageSize);
    }
    if length == 0 {
        return Ok(0);
    }
    let last = offset
        .checked_add(length - 1)
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(last / page_size - offset / page_size + 1)
}

/// Inputs to one serial screening estimate.
///
/// `payload_copy_passes` counts only the copies named by the caller. The
/// estimate adds modeled copy time, fixed system-call time, and `other_ns`. It
/// does not model overlap, queueing, page references, cache effects, protocol
/// work, encryption, or device movement.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PathCostInputs {
    /// Logical payload size in bytes.
    pub logical_bytes: u64,
    /// Complete copies of the logical payload included in this model.
    pub payload_copy_passes: u64,
    /// System calls included in this model.
    pub syscall_count: u64,
    /// Effective bandwidth of the named payload copies, in bytes per second.
    pub copy_bandwidth_bytes_per_second: u64,
    /// Fixed modeled cost per system call, in nanoseconds.
    pub fixed_syscall_ns: u64,
    /// Other serial cost assigned by the caller, in nanoseconds.
    pub other_ns: u64,
}

/// A serial screening estimate for one transfer path.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PathCostEstimate {
    /// Bytes moved by the named payload-copy passes.
    pub named_copy_bytes: u128,
    /// Named payload-copy time rounded up to a whole nanosecond.
    pub copy_ns: u128,
    /// Fixed system-call time.
    pub syscall_ns: u128,
    /// Sum of copy, system-call, and caller-supplied other time.
    pub total_ns: u128,
}

/// Baseline and copy-avoiding inputs for a like-for-like screen.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TransferCostInputs {
    /// Inputs for the baseline path.
    pub baseline: PathCostInputs,
    /// Inputs for the candidate that avoids at least one named copy.
    pub copy_avoiding: PathCostInputs,
}

/// Result of [`compare_transfer_costs`].
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct TransferCostComparison {
    /// Baseline serial estimate.
    pub baseline: PathCostEstimate,
    /// Copy-avoiding serial estimate.
    pub copy_avoiding: PathCostEstimate,
    /// Whether the copy-avoiding estimate is strictly smaller.
    pub copy_avoiding_wins: bool,
}

/// Compares a baseline with a copy-avoiding candidate under one declared model.
///
/// This is a candidate filter, not a benchmark predictor. Use the same
/// workload boundary for both inputs and put path-specific costs such as page
/// pinning or completion processing in `other_ns`.
///
/// # Errors
///
/// Returns [`ModelError::ZeroCopyBandwidth`] if either bandwidth is zero and
/// [`ModelError::ArithmeticOverflow`] if any intermediate does not fit `u128`.
pub fn compare_transfer_costs(
    inputs: TransferCostInputs,
) -> Result<TransferCostComparison, ModelError> {
    let baseline = estimate_path_cost(inputs.baseline)?;
    let copy_avoiding = estimate_path_cost(inputs.copy_avoiding)?;
    Ok(TransferCostComparison {
        baseline,
        copy_avoiding,
        copy_avoiding_wins: copy_avoiding.total_ns < baseline.total_ns,
    })
}

fn estimate_path_cost(inputs: PathCostInputs) -> Result<PathCostEstimate, ModelError> {
    if inputs.copy_bandwidth_bytes_per_second == 0 {
        return Err(ModelError::ZeroCopyBandwidth);
    }
    let named_copy_bytes = u128::from(inputs.logical_bytes)
        .checked_mul(u128::from(inputs.payload_copy_passes))
        .ok_or(ModelError::ArithmeticOverflow)?;
    let copy_ns = named_copy_bytes
        .checked_mul(NANOS_PER_SECOND)
        .ok_or(ModelError::ArithmeticOverflow)?
        .div_ceil(u128::from(inputs.copy_bandwidth_bytes_per_second));
    let syscall_ns = u128::from(inputs.syscall_count)
        .checked_mul(u128::from(inputs.fixed_syscall_ns))
        .ok_or(ModelError::ArithmeticOverflow)?;
    let total_ns = copy_ns
        .checked_add(syscall_ns)
        .and_then(|value| value.checked_add(u128::from(inputs.other_ns)))
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(PathCostEstimate {
        named_copy_bytes,
        copy_ns,
        syscall_ns,
        total_ns,
    })
}

/// Lower-bound call accounting for an explicit `splice` pipe.
#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct PipeTransferEstimate {
    /// Most bytes one modeled fill-and-drain cycle can move.
    pub bytes_per_cycle: u64,
    /// Minimum complete fill-and-drain cycles for the logical payload.
    pub cycles: u64,
    /// Minimum `splice` calls: one fill and one drain per cycle.
    pub minimum_splice_calls: u64,
}

/// Computes a lower bound for a bounded file-to-pipe-to-socket transfer.
///
/// The effective cycle size is the smaller of `pipe_capacity` and
/// `requested_chunk`. Real calls may return short progress, so the observed
/// call count can only be equal or higher for the same transfer.
///
/// # Errors
///
/// Returns [`ModelError::ZeroPipeCapacity`] or [`ModelError::ZeroChunkSize`]
/// for a zero bound, and [`ModelError::ArithmeticOverflow`] if twice the cycle
/// count does not fit `u64`.
pub fn splice_pipe_estimate(
    logical_bytes: u64,
    pipe_capacity: u64,
    requested_chunk: u64,
) -> Result<PipeTransferEstimate, ModelError> {
    if pipe_capacity == 0 {
        return Err(ModelError::ZeroPipeCapacity);
    }
    if requested_chunk == 0 {
        return Err(ModelError::ZeroChunkSize);
    }
    let bytes_per_cycle = pipe_capacity.min(requested_chunk);
    let cycles = if logical_bytes == 0 {
        0
    } else {
        logical_bytes
            .checked_sub(1)
            .and_then(|value| value.checked_div(bytes_per_cycle))
            .and_then(|value| value.checked_add(1))
            .ok_or(ModelError::ArithmeticOverflow)?
    };
    let minimum_splice_calls = cycles
        .checked_mul(2)
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(PipeTransferEstimate {
        bytes_per_cycle,
        cycles,
        minimum_splice_calls,
    })
}

/// Estimates average bytes whose reuse waits for asynchronous completion.
///
/// This is Little's-law accounting: sends per second multiplied by bytes per
/// send and mean completion latency. The result rounds upward to a whole byte.
/// It is a capacity estimate, not a percentile bound.
///
/// # Errors
///
/// Returns [`ModelError::ArithmeticOverflow`] if an intermediate does not fit
/// in `u128`.
pub fn held_bytes(
    sends_per_second: u64,
    bytes_per_send: u64,
    completion_latency_ns: u64,
) -> Result<u128, ModelError> {
    let byte_nanos = u128::from(sends_per_second)
        .checked_mul(u128::from(bytes_per_send))
        .and_then(|value| value.checked_mul(u128::from(completion_latency_ns)))
        .ok_or(ModelError::ArithmeticOverflow)?;
    Ok(byte_nanos.div_ceil(NANOS_PER_SECOND))
}

/// Reports whether an inclusive 32-bit completion range covers `id`.
///
/// Linux `MSG_ZEROCOPY` completion identifiers wrap after `u32::MAX`. A range
/// with `first > last` therefore crosses zero. This helper does not establish
/// that a kernel notification is authentic or belongs to the expected socket.
pub const fn completion_range_covers(first: u32, last: u32, id: u32) -> bool {
    if first <= last {
        first <= id && id <= last
    } else {
        id >= first || id <= last
    }
}

/// Tracks storage whose reuse waits for Linux `MSG_ZEROCOPY` completion IDs.
///
/// One successful, nonempty `send` that requests `MSG_ZEROCOPY` consumes the
/// next 32-bit identifier. The caller must retain its identifier-to-storage
/// mapping until [`Self::complete_range`] returns that identifier. A completion
/// permits storage reuse; it does not prove remote delivery. The kernel's
/// copied-fallback notification also ends the lifetime and should be passed to
/// this tracker after the caller validates its error-queue origin.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct CompletionTracker {
    next_id: u32,
    outstanding: BTreeSet<u32>,
}

impl CompletionTracker {
    /// Creates an empty tracker whose first submission uses identifier zero.
    #[must_use]
    pub fn new() -> Self {
        Self::with_next_id(0)
    }

    /// Creates an empty tracker with an explicit next identifier.
    ///
    /// This constructor makes wrap behavior testable. Production callers
    /// should normally use [`Self::new`] and keep one tracker per socket.
    #[must_use]
    pub fn with_next_id(next_id: u32) -> Self {
        Self {
            next_id,
            outstanding: BTreeSet::new(),
        }
    }

    /// Records one successful, nonempty submission and returns its identifier.
    ///
    /// # Errors
    ///
    /// Returns [`ModelError::IdentifierStillOutstanding`] if a complete
    /// 32-bit wrap would reuse an identifier whose old buffer is still held.
    pub fn submit(&mut self) -> Result<u32, ModelError> {
        let id = self.next_id;
        if !self.outstanding.insert(id) {
            return Err(ModelError::IdentifierStillOutstanding(id));
        }
        self.next_id = self.next_id.wrapping_add(1);
        Ok(id)
    }

    /// Applies one inclusive completion range and returns newly reusable IDs.
    ///
    /// The returned vector is in ascending numeric order, not submission
    /// order. Duplicate or overlapping notifications return only IDs that were
    /// still outstanding. Callers must validate the notification's socket,
    /// origin, error code, and zero-copy code before calling this method.
    pub fn complete_range(&mut self, first: u32, last: u32) -> Vec<u32> {
        let completed: Vec<u32> = self
            .outstanding
            .iter()
            .copied()
            .filter(|id| completion_range_covers(first, last, *id))
            .collect();
        for id in &completed {
            self.outstanding.remove(id);
        }
        completed
    }

    /// Reports whether the storage for an identifier must remain alive.
    #[must_use]
    pub fn is_outstanding(&self, id: u32) -> bool {
        self.outstanding.contains(&id)
    }

    /// Returns the number of submitted identifiers without completion.
    #[must_use]
    pub fn outstanding_len(&self) -> usize {
        self.outstanding.len()
    }
}

impl Default for CompletionTracker {
    fn default() -> Self {
        Self::new()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn buffered_path_counts_two_named_copies() {
        let accounting = file_path_accounting(FilePath::Buffered, 64).unwrap();
        assert_eq!(accounting.named_payload_copy_bytes, 128);
        assert!(accounting.application_buffer_exposed);
        assert!(!accounting.explicit_pipe);
    }

    #[test]
    fn kernel_paths_do_not_claim_total_zero_copy() {
        let sendfile = file_path_accounting(FilePath::Sendfile, 64).unwrap();
        let splice = file_path_accounting(FilePath::Splice, 64).unwrap();
        assert_eq!(sendfile.named_payload_copy_bytes, 0);
        assert_eq!(splice.named_payload_copy_bytes, 0);
        assert!(splice.explicit_pipe);
    }

    #[test]
    fn page_span_accounts_for_unaligned_ends() {
        assert_eq!(pages_spanned(0, 0, 4096), Ok(0));
        assert_eq!(pages_spanned(0, 4096, 4096), Ok(1));
        assert_eq!(pages_spanned(4095, 2, 4096), Ok(2));
        assert_eq!(
            pages_spanned(2, u64::MAX, 4096),
            Err(ModelError::ArithmeticOverflow)
        );
    }

    #[test]
    fn cost_model_checks_inputs_and_accounts_serial_terms() {
        let comparison = compare_transfer_costs(TransferCostInputs {
            baseline: PathCostInputs {
                logical_bytes: 64 * 1024 * 1024,
                payload_copy_passes: 2,
                syscall_count: 128,
                copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
                fixed_syscall_ns: 200,
                other_ns: 0,
            },
            copy_avoiding: PathCostInputs {
                logical_bytes: 64 * 1024 * 1024,
                payload_copy_passes: 0,
                syscall_count: 64,
                copy_bandwidth_bytes_per_second: 20 * 1024 * 1024 * 1024,
                fixed_syscall_ns: 200,
                other_ns: 0,
            },
        })
        .unwrap();
        assert_eq!(comparison.baseline.named_copy_bytes, 128 * 1024 * 1024);
        assert_eq!(comparison.baseline.copy_ns, 6_250_000);
        assert_eq!(comparison.baseline.syscall_ns, 25_600);
        assert_eq!(comparison.baseline.total_ns, 6_275_600);
        assert_eq!(comparison.copy_avoiding.total_ns, 12_800);
        assert!(comparison.copy_avoiding_wins);

        let invalid = PathCostInputs {
            copy_bandwidth_bytes_per_second: 0,
            ..comparison_input()
        };
        assert_eq!(
            estimate_path_cost(invalid),
            Err(ModelError::ZeroCopyBandwidth)
        );
    }

    fn comparison_input() -> PathCostInputs {
        PathCostInputs {
            logical_bytes: 1,
            payload_copy_passes: 1,
            syscall_count: 1,
            copy_bandwidth_bytes_per_second: 1,
            fixed_syscall_ns: 1,
            other_ns: 1,
        }
    }

    #[test]
    fn bounded_pipe_sets_a_call_count_floor() {
        let estimate = splice_pipe_estimate(64 * 1024 * 1024, 64 * 1024, 1024 * 1024).unwrap();
        assert_eq!(estimate.bytes_per_cycle, 64 * 1024);
        assert_eq!(estimate.cycles, 1024);
        assert_eq!(estimate.minimum_splice_calls, 2048);
        assert_eq!(
            splice_pipe_estimate(1, 0, 1),
            Err(ModelError::ZeroPipeCapacity)
        );
    }

    #[test]
    fn held_memory_scales_with_completion_latency() {
        assert_eq!(held_bytes(20_000, 64 * 1024, 5_000_000), Ok(6_553_600));
        assert_eq!(held_bytes(20_000, 64 * 1024, 100_000_000), Ok(131_072_000));
    }

    #[test]
    fn completion_tracker_handles_coalescing_order_and_wrap() {
        let mut tracker = CompletionTracker::with_next_id(u32::MAX - 1);
        let ids = [
            tracker.submit().unwrap(),
            tracker.submit().unwrap(),
            tracker.submit().unwrap(),
            tracker.submit().unwrap(),
        ];
        assert_eq!(ids, [u32::MAX - 1, u32::MAX, 0, 1]);

        let completed = tracker.complete_range(u32::MAX, 0);
        assert_eq!(completed, vec![0, u32::MAX]);
        assert!(!tracker.is_outstanding(u32::MAX));
        assert!(!tracker.is_outstanding(0));
        assert!(tracker.is_outstanding(u32::MAX - 1));
        assert!(tracker.is_outstanding(1));
        assert_eq!(tracker.outstanding_len(), 2);

        assert_eq!(tracker.complete_range(u32::MAX, 0), Vec::<u32>::new());
        assert_eq!(tracker.complete_range(1, 1), vec![1]);
        assert_eq!(
            tracker.complete_range(u32::MAX - 1, u32::MAX - 1),
            vec![u32::MAX - 1]
        );
        assert_eq!(tracker.outstanding_len(), 0);
    }
}
