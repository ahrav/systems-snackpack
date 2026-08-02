//! A non-causal cycle-accounting model for CPU frontend experiments.
//!
//! The model separates operation supply from exposed event penalties. It
//! accepts exposed, non-overlapped cycles rather than raw miss latency because
//! other work can hide latency. The estimate can test whether measured counts
//! and assumed costs explain an observation; it cannot identify which
//! microarchitectural structure caused the observation.
//!
//! # Model boundary
//!
//! [`estimate_frontend_cycles`] adds two supply-time terms, one path-transition
//! term, and three event-penalty terms. It neither derives penalties from
//! performance-monitoring counters nor models overlap among the terms.
//! [`phase_cycle_floor`] reports the larger requirement. Complete overlap makes
//! that lower bound tight; serialization raises the observed cycle count.
//!
//! # Example
//!
//! ```
//! use cpu_frontend_bottlenecks::{
//!     ExposedPenalty, FrontendInputs, SupplyTerm, estimate_frontend_cycles,
//! };
//!
//! let estimate = estimate_frontend_cycles(FrontendInputs {
//!     cached_supply: SupplyTerm::new(600.0, 8.0),
//!     decode_supply: SupplyTerm::new(400.0, 5.0),
//!     path_switch_cycles: 3.0,
//!     instruction_refills: ExposedPenalty::new(2.0, 7.0),
//!     translation_misses: ExposedPenalty::new(1.0, 12.0),
//!     redirects: ExposedPenalty::new(4.0, 5.0),
//! })
//! .expect("example inputs satisfy the model domain");
//!
//! assert_eq!(estimate.supply_cycles, 155.0);
//! assert_eq!(estimate.total_cycles, 204.0);
//! ```

#![forbid(unsafe_code)]

/// Operations delivered through one frontend supply path.
///
/// `operations_per_cycle` represents a workload-specific sustainable rate. A
/// vendor peak width is not a measured sustainable rate.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct SupplyTerm {
    /// Operations attributed to this path during the modeled phase.
    pub operations: f64,
    /// Sustainable delivery rate for this path, in operations per cycle.
    pub operations_per_cycle: f64,
}

impl SupplyTerm {
    /// Stores a phase operation count and delivery rate without validation.
    ///
    /// [`estimate_frontend_cycles`] accepts `operations` only when it is finite
    /// and non-negative, and `operations_per_cycle` only when it is finite and
    /// strictly positive.
    ///
    /// # Examples
    ///
    /// ```
    /// use cpu_frontend_bottlenecks::SupplyTerm;
    ///
    /// let decoder = SupplyTerm::new(400.0, 5.0);
    /// assert_eq!(decoder.operations / decoder.operations_per_cycle, 80.0);
    /// ```
    #[must_use]
    pub const fn new(operations: f64, operations_per_cycle: f64) -> Self {
        Self {
            operations,
            operations_per_cycle,
        }
    }
}

/// An event count multiplied by its exposed, non-overlapped cycle cost.
///
/// Use scaled counts when a performance-monitoring unit reports multiplexed
/// events. Raw miss latency overstates this term when other work hides latency.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ExposedPenalty {
    /// Events observed or estimated during the modeled phase.
    pub events: f64,
    /// Non-overlapped cycles exposed by one event.
    pub exposed_cycles_per_event: f64,
}

impl ExposedPenalty {
    /// Stores an event count and exposed cost without validation.
    ///
    /// [`estimate_frontend_cycles`] accepts both values only when they are
    /// finite and non-negative. Their product must also remain finite.
    ///
    /// # Examples
    ///
    /// ```
    /// use cpu_frontend_bottlenecks::ExposedPenalty;
    ///
    /// let refills = ExposedPenalty::new(2.0, 7.0);
    /// assert_eq!(refills.events * refills.exposed_cycles_per_event, 14.0);
    /// ```
    #[must_use]
    pub const fn new(events: f64, exposed_cycles_per_event: f64) -> Self {
        Self {
            events,
            exposed_cycles_per_event,
        }
    }

    fn cycles(self) -> Option<f64> {
        if !is_non_negative_finite(self.events)
            || !is_non_negative_finite(self.exposed_cycles_per_event)
        {
            return None;
        }

        finite_product(self.events, self.exposed_cycles_per_event)
    }
}

/// Inputs to the two-path frontend accounting model.
///
/// “Cached” covers an implementation-specific decoded-operation or
/// macro-operation cache. “Decode” covers delivery through instruction bytes
/// and decoders. Neither name asserts that a target implements a named Intel,
/// AMD, or Arm structure.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FrontendInputs {
    /// Work supplied by the implementation-specific cached-operation path.
    pub cached_supply: SupplyTerm,
    /// Work supplied by the instruction-byte and decoder path.
    pub decode_supply: SupplyTerm,
    /// Exposed cycles attributed to transitions between supply paths.
    pub path_switch_cycles: f64,
    /// Exposed instruction-cache refill cost.
    pub instruction_refills: ExposedPenalty,
    /// Exposed instruction-address translation cost.
    pub translation_misses: ExposedPenalty,
    /// Exposed branch-redirect and recovery cost.
    pub redirects: ExposedPenalty,
}

/// Cycle breakdown from [`estimate_frontend_cycles`].
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct FrontendEstimate {
    /// Sum of `operations / operations_per_cycle` across both supply paths.
    pub supply_cycles: f64,
    /// Exposed cycles attributed to transitions between supply paths.
    pub path_switch_cycles: f64,
    /// Exposed instruction-cache refill cycles.
    pub instruction_refill_cycles: f64,
    /// Exposed instruction-address translation cycles.
    pub translation_cycles: f64,
    /// Exposed redirect and recovery cycles.
    pub redirect_cycles: f64,
    /// Sum of all modeled frontend terms.
    pub total_cycles: f64,
}

/// Adds two supply times, one path-transition cost, and three event penalties.
///
/// The result preserves each penalty as a separate field for comparison with
/// measured evidence. It returns no causal attribution: multiple frontend
/// structures can change together after one layout change.
///
/// Returns `None` when any input is negative or non-finite, a supply rate is
/// zero, or a quotient, product, or sum becomes non-finite.
///
/// # Examples
///
/// ```
/// use cpu_frontend_bottlenecks::{
///     ExposedPenalty, FrontendInputs, SupplyTerm, estimate_frontend_cycles,
/// };
///
/// let estimate = estimate_frontend_cycles(FrontendInputs {
///     cached_supply: SupplyTerm::new(80.0, 8.0),
///     decode_supply: SupplyTerm::new(25.0, 5.0),
///     path_switch_cycles: 1.0,
///     instruction_refills: ExposedPenalty::new(1.0, 4.0),
///     translation_misses: ExposedPenalty::new(0.0, 0.0),
///     redirects: ExposedPenalty::new(2.0, 3.0),
/// })
/// .expect("valid model");
///
/// assert_eq!(estimate.total_cycles, 26.0);
/// ```
#[must_use]
pub fn estimate_frontend_cycles(inputs: FrontendInputs) -> Option<FrontendEstimate> {
    let cached_cycles = supply_cycles(inputs.cached_supply)?;
    let decode_cycles = supply_cycles(inputs.decode_supply)?;
    let supply_cycles = finite_sum(&[cached_cycles, decode_cycles])?;

    if !is_non_negative_finite(inputs.path_switch_cycles) {
        return None;
    }

    let instruction_refill_cycles = inputs.instruction_refills.cycles()?;
    let translation_cycles = inputs.translation_misses.cycles()?;
    let redirect_cycles = inputs.redirects.cycles()?;
    let total_cycles = finite_sum(&[
        supply_cycles,
        inputs.path_switch_cycles,
        instruction_refill_cycles,
        translation_cycles,
        redirect_cycles,
    ])?;

    Some(FrontendEstimate {
        supply_cycles,
        path_switch_cycles: inputs.path_switch_cycles,
        instruction_refill_cycles,
        translation_cycles,
        redirect_cycles,
        total_cycles,
    })
}

/// Returns the larger frontend or backend cycle requirement.
///
/// The result is a lower bound when the phase must satisfy both requirements.
/// Complete overlap makes the bound tight; serialization and dependency costs
/// increase the observed cycle count.
///
/// Returns `None` when either input is negative or non-finite.
///
/// # Examples
///
/// ```
/// use cpu_frontend_bottlenecks::phase_cycle_floor;
///
/// assert_eq!(phase_cycle_floor(204.0, 180.0), Some(204.0));
/// assert_eq!(phase_cycle_floor(204.0, 250.0), Some(250.0));
/// ```
#[must_use]
pub fn phase_cycle_floor(frontend_cycles: f64, backend_cycles: f64) -> Option<f64> {
    if !is_non_negative_finite(frontend_cycles) || !is_non_negative_finite(backend_cycles) {
        return None;
    }

    Some(frontend_cycles.max(backend_cycles))
}

/// Workload counts and per-execution costs for a cold-outlining decision.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OutliningInputs {
    /// Hot-path executions in the target workload.
    pub hot_executions: f64,
    /// Cold-path executions in the target workload.
    pub cold_executions: f64,
    /// Frontend cycles removed from each hot-path execution.
    pub hot_cycles_saved_per_execution: f64,
    /// Cycles added to each cold-path execution.
    pub cold_cycles_added_per_execution: f64,
}

/// Cycle accounting for a cold-outlining decision.
#[derive(Clone, Copy, Debug, PartialEq)]
pub struct OutliningDecision {
    /// Total cycles removed from hot executions.
    pub hot_cycles_saved: f64,
    /// Total cycles added to cold executions.
    pub cold_cycles_added: f64,
    /// `hot_cycles_saved - cold_cycles_added`.
    pub net_cycles_saved: f64,
    /// Whether hot savings strictly exceed cold costs.
    pub beneficial: bool,
}

/// Evaluates the cold-outlining break-even rule.
///
/// The treatment is beneficial when the computed finite `f64` hot product
/// exceeds the computed cold product. Equality after floating-point rounding
/// is break-even, not a benefit; inputs near the boundary can round to equal
/// products.
///
/// Returns `None` when an input is negative or non-finite, or arithmetic
/// overflows to a non-finite value.
///
/// # Examples
///
/// ```
/// use cpu_frontend_bottlenecks::{OutliningInputs, evaluate_outlining};
///
/// let decision = evaluate_outlining(OutliningInputs {
///     hot_executions: 1_000.0,
///     cold_executions: 10.0,
///     hot_cycles_saved_per_execution: 0.5,
///     cold_cycles_added_per_execution: 20.0,
/// })
/// .expect("valid workload model");
///
/// assert_eq!(decision.net_cycles_saved, 300.0);
/// assert!(decision.beneficial);
/// ```
#[must_use]
pub fn evaluate_outlining(inputs: OutliningInputs) -> Option<OutliningDecision> {
    let values = [
        inputs.hot_executions,
        inputs.cold_executions,
        inputs.hot_cycles_saved_per_execution,
        inputs.cold_cycles_added_per_execution,
    ];
    if values
        .into_iter()
        .any(|value| !is_non_negative_finite(value))
    {
        return None;
    }

    let hot_cycles_saved =
        finite_product(inputs.hot_executions, inputs.hot_cycles_saved_per_execution)?;
    let cold_cycles_added = finite_product(
        inputs.cold_executions,
        inputs.cold_cycles_added_per_execution,
    )?;
    let net_cycles_saved = hot_cycles_saved - cold_cycles_added;
    if !net_cycles_saved.is_finite() {
        return None;
    }

    Some(OutliningDecision {
        hot_cycles_saved,
        cold_cycles_added,
        net_cycles_saved,
        beneficial: hot_cycles_saved > cold_cycles_added,
    })
}

fn supply_cycles(term: SupplyTerm) -> Option<f64> {
    if !is_non_negative_finite(term.operations)
        || !term.operations_per_cycle.is_finite()
        || term.operations_per_cycle <= 0.0
    {
        return None;
    }

    let cycles = term.operations / term.operations_per_cycle;
    cycles.is_finite().then_some(cycles)
}

fn finite_product(left: f64, right: f64) -> Option<f64> {
    let product = left * right;
    product.is_finite().then_some(product)
}

fn finite_sum(values: &[f64]) -> Option<f64> {
    let sum = values.iter().sum::<f64>();
    sum.is_finite().then_some(sum)
}

fn is_non_negative_finite(value: f64) -> bool {
    value.is_finite() && value >= 0.0
}

#[cfg(test)]
mod tests {
    use super::{
        ExposedPenalty, FrontendInputs, OutliningInputs, SupplyTerm, estimate_frontend_cycles,
        evaluate_outlining, phase_cycle_floor,
    };

    fn valid_frontend_inputs() -> FrontendInputs {
        FrontendInputs {
            cached_supply: SupplyTerm::new(600.0, 8.0),
            decode_supply: SupplyTerm::new(400.0, 5.0),
            path_switch_cycles: 3.0,
            instruction_refills: ExposedPenalty::new(2.0, 7.0),
            translation_misses: ExposedPenalty::new(1.0, 12.0),
            redirects: ExposedPenalty::new(4.0, 5.0),
        }
    }

    #[test]
    fn frontend_estimate_preserves_term_boundaries() {
        let estimate = estimate_frontend_cycles(valid_frontend_inputs()).expect("valid inputs");
        assert_eq!(estimate.supply_cycles, 155.0);
        assert_eq!(estimate.path_switch_cycles, 3.0);
        assert_eq!(estimate.instruction_refill_cycles, 14.0);
        assert_eq!(estimate.translation_cycles, 12.0);
        assert_eq!(estimate.redirect_cycles, 20.0);
        assert_eq!(estimate.total_cycles, 204.0);
    }

    #[test]
    fn invalid_frontend_inputs_are_rejected() {
        let mut inputs = valid_frontend_inputs();
        inputs.decode_supply.operations_per_cycle = 0.0;
        assert_eq!(estimate_frontend_cycles(inputs), None);

        let mut inputs = valid_frontend_inputs();
        inputs.instruction_refills.events = f64::NAN;
        assert_eq!(estimate_frontend_cycles(inputs), None);

        let mut inputs = valid_frontend_inputs();
        inputs.redirects.exposed_cycles_per_event = -1.0;
        assert_eq!(estimate_frontend_cycles(inputs), None);
    }

    #[test]
    fn phase_floor_rejects_invalid_cycles() {
        assert_eq!(phase_cycle_floor(10.0, 20.0), Some(20.0));
        assert_eq!(phase_cycle_floor(-1.0, 20.0), None);
        assert_eq!(phase_cycle_floor(f64::INFINITY, 20.0), None);
    }

    #[test]
    fn outlining_uses_a_strict_break_even_rule() {
        let beneficial = evaluate_outlining(OutliningInputs {
            hot_executions: 1_000.0,
            cold_executions: 10.0,
            hot_cycles_saved_per_execution: 0.5,
            cold_cycles_added_per_execution: 20.0,
        })
        .expect("valid inputs");
        assert_eq!(beneficial.net_cycles_saved, 300.0);
        assert!(beneficial.beneficial);

        let break_even = evaluate_outlining(OutliningInputs {
            hot_executions: 400.0,
            cold_executions: 10.0,
            hot_cycles_saved_per_execution: 0.5,
            cold_cycles_added_per_execution: 20.0,
        })
        .expect("valid inputs");
        assert_eq!(break_even.net_cycles_saved, 0.0);
        assert!(!break_even.beneficial);
    }

    #[test]
    fn outlining_rejects_invalid_or_overflowing_inputs() {
        let invalid = OutliningInputs {
            hot_executions: -1.0,
            cold_executions: 0.0,
            hot_cycles_saved_per_execution: 1.0,
            cold_cycles_added_per_execution: 0.0,
        };
        assert_eq!(evaluate_outlining(invalid), None);

        let overflow = OutliningInputs {
            hot_executions: f64::MAX,
            cold_executions: 0.0,
            hot_cycles_saved_per_execution: 2.0,
            cold_cycles_added_per_execution: 0.0,
        };
        assert_eq!(evaluate_outlining(overflow), None);
    }
}
