//! Decision models for selecting a vector width from workload measurements.
//!
//! The models separate three questions: whether memory delivery or compute
//! execution caps steady-state throughput, how an observed clock ratio changes
//! a fixed-work time ratio, and when greater throughput repays a path's extra
//! fixed costs. They keep bandwidth, clock rate, throughput, dispatch, and
//! follow-on costs explicit instead of inferring performance from an
//! instruction-set name.

#![forbid(unsafe_code)]

#[derive(Clone, Copy, Debug, PartialEq)]
/// Inputs to the memory and compute ceilings in the roofline model.
pub struct ThroughputInputs {
    /// Sustained bytes per second for the measured workload and placement.
    pub memory_bandwidth_bytes_per_second: f64,
    /// Bytes transferred per useful element, including required reads and writes.
    pub bytes_per_element: f64,
    /// Cycles per second observed for the tested instruction mix.
    pub clock_hz: f64,
    /// Vector operations retired per cycle when the dependency graph permits it.
    pub vector_operations_per_cycle: f64,
    /// Useful elements updated by one vector operation.
    pub lanes_per_vector: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Costs for one dispatched path in the fixed-work model.
pub struct PathCost {
    /// Measured useful-element throughput after all active bottlenecks.
    pub useful_elements_per_second: f64,
    /// Dispatch and setup time paid before useful work, in nanoseconds.
    pub dispatch_ns: f64,
    /// Follow-on time attributed to this path after useful work, in nanoseconds.
    pub post_work_ns: f64,
}

fn positive_finite(value: f64) -> bool {
    value.is_finite() && value > 0.0
}

fn nonnegative_finite(value: f64) -> bool {
    value.is_finite() && value >= 0.0
}

#[must_use]
/// Returns the smaller of the memory and compute throughput ceilings.
///
/// The memory ceiling divides sustained bandwidth by bytes per useful element.
/// The compute ceiling multiplies observed clock rate, vector operations per
/// cycle, and useful lanes per operation. Returns `None` if any input is zero,
/// negative, or non-finite. Finite positive inputs can still produce
/// `Some(0.0)` or `Some(f64::INFINITY)` if a ceiling calculation underflows or
/// overflows.
///
/// # Examples
///
/// ```
/// use performance_portability_vector_width::{
///     ThroughputInputs, roofline_elements_per_second,
/// };
///
/// let inputs = ThroughputInputs {
///     memory_bandwidth_bytes_per_second: 32e9,
///     bytes_per_element: 8.0,
///     clock_hz: 3e9,
///     vector_operations_per_cycle: 2.0,
///     lanes_per_vector: 4.0,
/// };
/// assert_eq!(roofline_elements_per_second(inputs), Some(4e9));
/// ```
pub fn roofline_elements_per_second(inputs: ThroughputInputs) -> Option<f64> {
    let values = [
        inputs.memory_bandwidth_bytes_per_second,
        inputs.bytes_per_element,
        inputs.clock_hz,
        inputs.vector_operations_per_cycle,
        inputs.lanes_per_vector,
    ];
    if !values.into_iter().all(positive_finite) {
        return None;
    }

    let memory_bound = inputs.memory_bandwidth_bytes_per_second / inputs.bytes_per_element;
    let compute_bound =
        inputs.clock_hz * inputs.vector_operations_per_cycle * inputs.lanes_per_vector;
    Some(memory_bound.min(compute_bound))
}

#[must_use]
/// Returns the candidate-to-baseline fixed-work time ratio implied by the input ratios.
///
/// `cycle_work_ratio` is candidate core cycles divided by baseline core cycles
/// for the same useful work under a matched measurement scope. `clock_ratio`
/// is candidate cycles per second divided by baseline cycles per second. Do not
/// substitute an instruction-count ratio unless the two paths have equal
/// per-instruction cycle cost. The result divides `cycle_work_ratio` by
/// `clock_ratio`. Returns `None` for non-positive or non-finite inputs. Finite
/// positive inputs can still produce `Some(0.0)` or `Some(f64::INFINITY)` if the
/// division underflows or overflows.
///
/// # Examples
///
/// ```
/// use performance_portability_vector_width::clock_adjusted_time_ratio;
///
/// let ratio = clock_adjusted_time_ratio(0.5, 0.844_445).unwrap();
/// assert!((ratio - 0.592_105).abs() < 0.000_001);
/// ```
pub fn clock_adjusted_time_ratio(cycle_work_ratio: f64, clock_ratio: f64) -> Option<f64> {
    if !positive_finite(cycle_work_ratio) || !positive_finite(clock_ratio) {
        return None;
    }
    Some(cycle_work_ratio / clock_ratio)
}

#[must_use]
/// Returns the modeled time for `elements` useful updates, in nanoseconds.
///
/// The model adds dispatch, steady-state work, and attributed follow-on time;
/// zero elements still incur both fixed costs. Returns `None` if `elements` or
/// either fixed cost is negative or non-finite, throughput is non-positive or
/// non-finite, or the computed time is non-finite.
///
/// # Examples
///
/// ```
/// use performance_portability_vector_width::{PathCost, fixed_work_time_ns};
///
/// let path = PathCost {
///     useful_elements_per_second: 40e9,
///     dispatch_ns: 20.0,
///     post_work_ns: 0.0,
/// };
/// assert!((fixed_work_time_ns(4_096.0, path).unwrap() - 122.4).abs() < 1e-9);
/// ```
pub fn fixed_work_time_ns(elements: f64, path: PathCost) -> Option<f64> {
    if !nonnegative_finite(elements)
        || !positive_finite(path.useful_elements_per_second)
        || !nonnegative_finite(path.dispatch_ns)
        || !nonnegative_finite(path.post_work_ns)
    {
        return None;
    }
    let result =
        path.dispatch_ns + elements * 1e9 / path.useful_elements_per_second + path.post_work_ns;
    result.is_finite().then_some(result)
}

#[must_use]
/// Returns the useful-element count where a faster path repays its extra fixed cost.
///
/// Both paths require positive finite throughput, nonnegative finite fixed
/// costs, and a finite sum of those costs. The `candidate` must have strictly
/// greater throughput and a strictly greater `dispatch_ns + post_work_ns` than
/// the `baseline`. Returns `None` when either path is invalid, either ordering
/// condition fails, or floating-point arithmetic does not produce a positive
/// finite crossing.
///
/// # Examples
///
/// ```
/// use performance_portability_vector_width::{PathCost, break_even_elements};
///
/// let narrow = PathCost {
///     useful_elements_per_second: 40e9,
///     dispatch_ns: 20.0,
///     post_work_ns: 0.0,
/// };
/// let wide = PathCost {
///     useful_elements_per_second: 60e9,
///     dispatch_ns: 50.0,
///     post_work_ns: 270.0,
/// };
/// assert!((break_even_elements(narrow, wide).unwrap() - 36_000.0).abs() < 1e-6);
/// ```
pub fn break_even_elements(baseline: PathCost, candidate: PathCost) -> Option<f64> {
    fixed_work_time_ns(0.0, baseline)?;
    fixed_work_time_ns(0.0, candidate)?;

    let baseline_fixed = baseline.dispatch_ns + baseline.post_work_ns;
    let candidate_fixed = candidate.dispatch_ns + candidate.post_work_ns;
    if candidate.useful_elements_per_second <= baseline.useful_elements_per_second
        || candidate_fixed <= baseline_fixed
    {
        return None;
    }

    let fixed_delta_seconds = (candidate_fixed - baseline_fixed) / 1e9;
    let seconds_per_element_delta =
        1.0 / baseline.useful_elements_per_second - 1.0 / candidate.useful_elements_per_second;
    let result = fixed_delta_seconds / seconds_per_element_delta;
    positive_finite(result).then_some(result)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roofline_selects_memory_bound() {
        let inputs = ThroughputInputs {
            memory_bandwidth_bytes_per_second: 32e9,
            bytes_per_element: 8.0,
            clock_hz: 2.5e9,
            vector_operations_per_cycle: 2.0,
            lanes_per_vector: 8.0,
        };
        assert_eq!(roofline_elements_per_second(inputs), Some(4e9));
    }

    #[test]
    fn roofline_selects_compute_bound() {
        let inputs = ThroughputInputs {
            memory_bandwidth_bytes_per_second: 1e12,
            bytes_per_element: 8.0,
            clock_hz: 2e9,
            vector_operations_per_cycle: 1.0,
            lanes_per_vector: 4.0,
        };
        assert_eq!(roofline_elements_per_second(inputs), Some(8e9));
    }

    #[test]
    fn fixed_work_example_changes_winner() {
        let narrow = PathCost {
            useful_elements_per_second: 40e9,
            dispatch_ns: 20.0,
            post_work_ns: 0.0,
        };
        let wide = PathCost {
            useful_elements_per_second: 60e9,
            dispatch_ns: 50.0,
            post_work_ns: 270.0,
        };

        assert!(fixed_work_time_ns(4_096.0, narrow) < fixed_work_time_ns(4_096.0, wide));
        assert!(fixed_work_time_ns(1_000_000.0, wide) < fixed_work_time_ns(1_000_000.0, narrow));
        assert_eq!(break_even_elements(narrow, wide), Some(36_000.0));
    }

    #[test]
    fn invalid_inputs_do_not_create_decisions() {
        let invalid = PathCost {
            useful_elements_per_second: 0.0,
            dispatch_ns: 1.0,
            post_work_ns: 1.0,
        };
        assert_eq!(fixed_work_time_ns(1.0, invalid), None);
        assert_eq!(clock_adjusted_time_ratio(0.5, 0.0), None);
        assert_eq!(break_even_elements(invalid, invalid), None);
    }
}
