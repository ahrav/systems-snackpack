//! Narrow models for reasoning about Extended Berkeley Packet Filter internals.
//!
//! An Extended Berkeley Packet Filter (eBPF) program is admitted, attached,
//! executed, and owned through separate Linux contracts. This crate models two
//! small parts that are useful without a Linux eBPF runtime:
//!
//! - [`ControlFlowProgram`] checks branch targets in a deliberately tiny
//!   instruction subset. It demonstrates why verifier acceptance is a separate
//!   step; it is not the Linux verifier.
//! - [`EventCost`] and the capacity functions make setup, per-event work,
//!   per-central-processing-unit (CPU) memory, and ring-buffer pressure
//!   explicit.
//!
//! Run `cargo run --package ebpf-internals --example cost-and-control` for the
//! deterministic example. The separate C experiment exercises the real Linux
//! `bpf()` system call and socket-filter path.

use std::error::Error;
use std::fmt::{self, Display, Formatter};

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// One instruction in the control-flow model.
///
/// The model includes only the operations needed to show a valid constant
/// return and an invalid out-of-range jump. It omits registers, memory,
/// helpers, references, pointer kinds, and every program-type rule enforced by
/// the Linux verifier.
pub enum ModelInstruction {
    /// Set the modeled return register to one signed 32-bit immediate value.
    MoveReturnImmediate(i32),
    /// Jump by a signed instruction offset relative to the following instruction.
    JumpAlways(i16),
    /// Return from the program.
    Exit,
}

#[derive(Clone, Debug, Eq, PartialEq)]
/// A deliberately small eBPF-like control-flow program.
pub struct ControlFlowProgram {
    instructions: Vec<ModelInstruction>,
}

impl ControlFlowProgram {
    #[must_use]
    /// Creates a program from the supplied model instructions.
    ///
    /// # Examples
    ///
    /// ```
    /// use ebpf_internals::{ControlFlowProgram, ModelInstruction};
    ///
    /// let program = ControlFlowProgram::new(vec![ModelInstruction::Exit]);
    /// assert_eq!(program.instructions(), &[ModelInstruction::Exit]);
    /// ```
    pub fn new(instructions: Vec<ModelInstruction>) -> Self {
        Self { instructions }
    }

    #[must_use]
    /// Returns the model instructions in submission order.
    ///
    /// # Examples
    ///
    /// ```
    /// use ebpf_internals::{ControlFlowProgram, ModelInstruction};
    ///
    /// let program = ControlFlowProgram::new(vec![ModelInstruction::Exit]);
    /// assert_eq!(program.instructions().len(), 1);
    /// ```
    pub fn instructions(&self) -> &[ModelInstruction] {
        &self.instructions
    }

    /// Checks the model's branch-target and final-exit rules.
    ///
    /// # Errors
    ///
    /// Returns [`ControlFlowError::EmptyProgram`] for an empty program,
    /// [`ControlFlowError::JumpOutOfRange`] when a jump target is outside the
    /// submitted instruction array, or [`ControlFlowError::MissingFinalExit`]
    /// when the last instruction is not [`ModelInstruction::Exit`]. Passing
    /// this check does not imply that the Linux verifier would accept a real
    /// program.
    ///
    /// # Examples
    ///
    /// ```
    /// use ebpf_internals::{ControlFlowProgram, ModelInstruction};
    ///
    /// let program = ControlFlowProgram::new(vec![
    ///     ModelInstruction::MoveReturnImmediate(0),
    ///     ModelInstruction::Exit,
    /// ]);
    /// assert_eq!(program.check(), Ok(()));
    /// ```
    pub fn check(&self) -> Result<(), ControlFlowError> {
        if self.instructions.is_empty() {
            return Err(ControlFlowError::EmptyProgram);
        }

        for (index, instruction) in self.instructions.iter().enumerate() {
            if let ModelInstruction::JumpAlways(offset) = instruction {
                let target = index as i64 + 1 + i64::from(*offset);
                if target < 0 || target >= self.instructions.len() as i64 {
                    return Err(ControlFlowError::JumpOutOfRange {
                        instruction: index,
                        target,
                    });
                }
            }
        }

        if self.instructions.last() != Some(&ModelInstruction::Exit) {
            return Err(ControlFlowError::MissingFinalExit);
        }
        Ok(())
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// A rejection reported by [`ControlFlowProgram::check`].
pub enum ControlFlowError {
    /// No instruction was supplied.
    EmptyProgram,
    /// One unconditional jump targets an instruction outside the program.
    JumpOutOfRange {
        /// Zero-based index of the rejected jump.
        instruction: usize,
        /// Signed target index computed relative to the next instruction.
        target: i64,
    },
    /// The model program does not end with an exit instruction.
    MissingFinalExit,
}

impl Display for ControlFlowError {
    fn fmt(&self, formatter: &mut Formatter<'_>) -> fmt::Result {
        match self {
            Self::EmptyProgram => formatter.write_str("program is empty"),
            Self::JumpOutOfRange {
                instruction,
                target,
            } => write!(
                formatter,
                "jump at instruction {instruction} targets instruction {target}, outside the program"
            ),
            Self::MissingFinalExit => formatter.write_str("program does not end with exit"),
        }
    }
}

impl Error for ControlFlowError {}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Per-event work split into independently measurable terms.
///
/// All fields use nanoseconds only to keep the arithmetic concrete. Constructing
/// this value does not measure any term.
pub struct EventCost {
    /// Entry to and return from the selected kernel hook.
    pub hook_ns: u64,
    /// Native instructions emitted for the eBPF body.
    pub native_ns: u64,
    /// Approved kernel helper calls made by the program.
    pub helpers_ns: u64,
    /// Map lookup, update, allocation, and hashing work.
    pub maps_ns: u64,
    /// Publication and notification work for output records.
    pub export_ns: u64,
    /// Delay caused by shared state, cache-line ownership, or locks.
    pub contention_ns: u64,
}

impl EventCost {
    #[must_use]
    /// Adds all six terms, returning `None` if `u64` arithmetic overflows.
    ///
    /// # Examples
    ///
    /// ```
    /// use ebpf_internals::EventCost;
    ///
    /// let cost = EventCost {
    ///     hook_ns: 8,
    ///     native_ns: 12,
    ///     helpers_ns: 15,
    ///     maps_ns: 18,
    ///     export_ns: 7,
    ///     contention_ns: 20,
    /// };
    /// assert_eq!(cost.total_nanoseconds(), Some(80));
    /// ```
    pub fn total_nanoseconds(self) -> Option<u64> {
        self.hook_ns
            .checked_add(self.native_ns)?
            .checked_add(self.helpers_ns)?
            .checked_add(self.maps_ns)?
            .checked_add(self.export_ns)?
            .checked_add(self.contention_ns)
    }
}

#[must_use]
/// Divides one-time setup cost across the events that use the loaded program.
///
/// `setup_nanoseconds` includes only costs the caller chooses to classify as
/// load, verification, relocation, map creation, and attachment. Returns
/// `None` when `event_count` is zero.
///
/// # Examples
///
/// ```
/// use ebpf_internals::amortized_setup_nanoseconds;
///
/// assert_eq!(amortized_setup_nanoseconds(12_000_000, 6_000_000), Some(2.0));
/// ```
pub fn amortized_setup_nanoseconds(setup_nanoseconds: u64, event_count: u64) -> Option<f64> {
    if event_count == 0 {
        None
    } else {
        Some(setup_nanoseconds as f64 / event_count as f64)
    }
}

#[must_use]
/// Rounds a byte count up to an eight-byte boundary.
///
/// Returns `None` when the rounded value would overflow `usize`.
///
/// # Examples
///
/// ```
/// use ebpf_internals::align_to_eight;
///
/// assert_eq!(align_to_eight(9), Some(16));
/// ```
pub fn align_to_eight(bytes: usize) -> Option<usize> {
    bytes.checked_add(7).map(|value| value & !7)
}

#[must_use]
/// Estimates payload bytes for a per-CPU map.
///
/// `possible_cpus` must be the kernel's possible CPU count rather than only the
/// CPUs online during one observation. `value_slots` is the number of allocated
/// values: `max_entries` for arrays and preallocated hashes, or the populated
/// entry count for a no-preallocation hash. `value_bytes` is the logical value
/// size. The estimate includes only eight-byte-aligned payloads. It excludes
/// map metadata, allocator overhead, and padding imposed by another map type.
///
/// # Examples
///
/// ```
/// use ebpf_internals::per_cpu_payload_bytes;
///
/// assert_eq!(per_cpu_payload_bytes(64, 1, 8), Some(512));
/// ```
pub fn per_cpu_payload_bytes(
    possible_cpus: usize,
    value_slots: usize,
    value_bytes: usize,
) -> Option<usize> {
    let aligned_value = align_to_eight(value_bytes)?;
    possible_cpus
        .checked_mul(value_slots)?
        .checked_mul(aligned_value)
}

#[must_use]
/// Returns the occupied bytes for one Linux BPF ring-buffer record.
///
/// Linux records have an eight-byte header and eight-byte alignment. Returns
/// `None` when header addition or alignment overflows `usize`.
///
/// # Examples
///
/// ```
/// use ebpf_internals::ring_record_bytes;
///
/// assert_eq!(ring_record_bytes(56), Some(64));
/// ```
pub fn ring_record_bytes(payload_bytes: usize) -> Option<usize> {
    align_to_eight(payload_bytes.checked_add(8)?)
}

#[must_use]
/// Calculates seconds until a ring buffer fills under constant overload.
///
/// `capacity_bytes` is usable ring capacity. `producer_records_per_second` is
/// the aggregate reservation rate. `payload_bytes` excludes the record header.
/// `consumer_bytes_per_second` is sustained drain bandwidth. Returns `None` for
/// non-finite or negative rates, arithmetic overflow, or a producer rate that
/// does not exceed the consumer rate. This is a capacity calculation; it does
/// not model burstiness, notification, scheduling, failed reservations, or a
/// producer that stalls while holding an earlier reservation.
///
/// # Examples
///
/// ```
/// use ebpf_internals::ring_fill_seconds;
///
/// let seconds = ring_fill_seconds(8_388_608, 2_000_000.0, 56, 100_000_000.0)
///     .expect("production exceeds consumption");
/// assert!((seconds - 0.299_593_142_857_142_9).abs() < 1e-12);
/// ```
pub fn ring_fill_seconds(
    capacity_bytes: usize,
    producer_records_per_second: f64,
    payload_bytes: usize,
    consumer_bytes_per_second: f64,
) -> Option<f64> {
    if !producer_records_per_second.is_finite()
        || !consumer_bytes_per_second.is_finite()
        || producer_records_per_second < 0.0
        || consumer_bytes_per_second < 0.0
    {
        return None;
    }
    let record_bytes = ring_record_bytes(payload_bytes)? as f64;
    let offered_bytes_per_second = producer_records_per_second * record_bytes;
    let deficit = offered_bytes_per_second - consumer_bytes_per_second;
    if !deficit.is_finite() || deficit <= 0.0 {
        return None;
    }
    Some(capacity_bytes as f64 / deficit)
}

#[must_use]
/// Computes an intentionally loose upper bound for independent binary paths.
///
/// If `binary_branches` decisions can vary independently and no states merge,
/// there can be `2^binary_branches` paths. The real Linux verifier performs
/// state equivalence and pruning, so this function is an intuition aid rather
/// than a verifier-complexity prediction. Returns `None` when the value does
/// not fit in `u128`.
///
/// # Examples
///
/// ```
/// use ebpf_internals::independent_binary_path_bound;
///
/// assert_eq!(independent_binary_path_bound(10), Some(1_024));
/// ```
pub const fn independent_binary_path_bound(binary_branches: u32) -> Option<u128> {
    1_u128.checked_shl(binary_branches)
}

#[cfg(test)]
mod tests {
    use super::{
        ControlFlowError, ControlFlowProgram, EventCost, ModelInstruction,
        amortized_setup_nanoseconds, independent_binary_path_bound, per_cpu_payload_bytes,
        ring_fill_seconds, ring_record_bytes,
    };

    #[test]
    fn valid_constant_return_passes_the_narrow_check() {
        let program = ControlFlowProgram::new(vec![
            ModelInstruction::MoveReturnImmediate(-1),
            ModelInstruction::Exit,
        ]);

        assert_eq!(program.check(), Ok(()));
    }

    #[test]
    fn out_of_range_jump_reports_source_and_target() {
        let program = ControlFlowProgram::new(vec![
            ModelInstruction::JumpAlways(100),
            ModelInstruction::Exit,
        ]);

        assert_eq!(
            program.check(),
            Err(ControlFlowError::JumpOutOfRange {
                instruction: 0,
                target: 101,
            })
        );
    }

    #[test]
    fn event_terms_and_setup_share_match_the_running_example() {
        let cost = EventCost {
            hook_ns: 8,
            native_ns: 12,
            helpers_ns: 15,
            maps_ns: 18,
            export_ns: 7,
            contention_ns: 20,
        };

        assert_eq!(cost.total_nanoseconds(), Some(80));
        assert_eq!(
            amortized_setup_nanoseconds(12_000_000, 6_000_000),
            Some(2.0)
        );
        assert_eq!(amortized_setup_nanoseconds(12_000_000, 0), None);
    }

    #[test]
    fn capacity_examples_preserve_headers_and_alignment() {
        assert_eq!(per_cpu_payload_bytes(64, 1, 8), Some(512));
        assert_eq!(ring_record_bytes(56), Some(64));
        let seconds = ring_fill_seconds(8_388_608, 2_000_000.0, 56, 100_000_000.0)
            .expect("the producer rate exceeds the consumer rate");
        assert!((seconds - 0.299_593_142_857_142_9).abs() < 1e-12);
        assert_eq!(
            ring_fill_seconds(8_388_608, 1_000_000.0, 56, 100_000_000.0),
            None
        );
    }

    #[test]
    fn independent_path_bound_is_explicitly_loose() {
        assert_eq!(independent_binary_path_bound(10), Some(1_024));
        assert_eq!(independent_binary_path_bound(128), None);
    }
}
