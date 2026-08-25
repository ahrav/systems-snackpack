//! First-order decision models for cache-line ownership costs.
//!
//! These functions do not infer coherence traffic from elapsed time or sampled
//! accesses. They make a layout decision's inputs explicit: completed updates,
//! ownership handoffs, handoff cost on the measured path, and the workload cost
//! of a larger memory footprint.

#![forbid(unsafe_code)]

fn nonnegative_finite(value: f64) -> bool {
    value.is_finite() && value >= 0.0
}

/// Estimates average cost per update from local work and ownership handoffs.
///
/// `handoffs` counts modeled or independently measured ownership transfers over
/// the same interval as `updates`. It is not a count of stores, cache-to-cache
/// samples, or invalidations. The result is `local_cost_ns +
/// handoffs / updates * handoff_cost_ns`.
///
/// Returns `None` when `updates` is zero, either cost is negative or non-finite,
/// or the computed result is non-finite. The calculation converts both counts
/// to `f64`; integers above 2^53 need not retain unit precision.
///
/// This first-order model omits overlap, retries, topology-dependent handoff
/// costs, and true-sharing serialization. Use a sum of path-specific handoff
/// costs when one constant cannot represent the measured topology.
///
/// # Examples
///
/// Twenty handoffs serve 1,000 updates. At 80 nanoseconds per handoff, each
/// update receives 1.6 nanoseconds of handoff cost:
///
/// ```
/// use cache_coherence_false_sharing::average_update_cost_ns;
///
/// assert_eq!(average_update_cost_ns(2.0, 20, 1_000, 80.0), Some(3.6));
/// ```
#[must_use]
pub fn average_update_cost_ns(
    local_cost_ns: f64,
    handoffs: u64,
    updates: u64,
    handoff_cost_ns: f64,
) -> Option<f64> {
    if updates == 0 || !nonnegative_finite(local_cost_ns) || !nonnegative_finite(handoff_cost_ns) {
        return None;
    }
    let result = local_cost_ns + handoffs as f64 / updates as f64 * handoff_cost_ns;
    result.is_finite().then_some(result)
}

/// Estimates the net time saved by separating two write-hot fields.
///
/// Both handoff counts must describe the same interval. `footprint_cost_ns` is
/// a measured or explicitly modeled workload cost from the larger layout; it is
/// not the number of padding bytes. A positive result favors the split layout.
/// A negative result favors the packed layout under these inputs.
///
/// Returns `None` when either cost is negative or non-finite, or when the
/// computed result is non-finite. The calculation converts both handoff counts
/// to `f64`; integers above 2^53 need not retain unit precision.
///
/// # Examples
///
/// Removing 90 handoffs at 80 nanoseconds each saves 7,200 nanoseconds. Paying
/// 1,000 nanoseconds for the larger footprint leaves a 6,200-nanosecond saving:
///
/// ```
/// use cache_coherence_false_sharing::split_layout_saving_ns;
///
/// assert_eq!(split_layout_saving_ns(100, 10, 80.0, 1_000.0), Some(6_200.0));
/// ```
#[must_use]
pub fn split_layout_saving_ns(
    packed_handoffs: u64,
    split_handoffs: u64,
    handoff_cost_ns: f64,
    footprint_cost_ns: f64,
) -> Option<f64> {
    if !nonnegative_finite(handoff_cost_ns) || !nonnegative_finite(footprint_cost_ns) {
        return None;
    }
    let avoided_handoffs = packed_handoffs as f64 - split_handoffs as f64;
    let result = avoided_handoffs * handoff_cost_ns - footprint_cost_ns;
    result.is_finite().then_some(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn average_cost_rejects_invalid_inputs() {
        assert_eq!(average_update_cost_ns(1.0, 0, 0, 1.0), None);
        assert_eq!(average_update_cost_ns(-1.0, 0, 1, 1.0), None);
        assert_eq!(average_update_cost_ns(1.0, 0, 1, f64::NAN), None);
    }

    #[test]
    fn split_model_can_favor_packing() {
        assert_eq!(
            split_layout_saving_ns(10, 10, 80.0, 1_000.0),
            Some(-1_000.0)
        );
        assert_eq!(split_layout_saving_ns(10, 0, f64::INFINITY, 0.0), None);
    }
}
