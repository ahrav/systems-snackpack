//! Pure cost accounting for NUMA placement decisions.
//!
//! NUMA (non-uniform memory access) systems attach memory to different nodes.
//! [`classify_access`] compares the worker's node with a page's observed node.
//! The remaining functions compare exposed, non-overlapped access costs with
//! migration and replication overhead.
//!
//! This crate does not discover topology, establish that first touch caused an
//! observed placement, place pages, migrate memory, or predict elapsed time
//! from a vendor distance number. A lowest-cost result does not establish that
//! the selected strategy is operationally feasible. Supply measured inputs from one
//! declared workload and decision horizon.
//!
//! # Example
//!
//! ```
//! use numa_first_touch_migration::{
//!     AccessLocality, LatencyInputs, classify_access, estimate_latency_cost,
//!     migration_break_even_accesses,
//! };
//!
//! assert_eq!(classify_access(1, 0), AccessLocality::Remote);
//!
//! let cost = estimate_latency_cost(LatencyInputs {
//!     local_accesses: 900.0,
//!     remote_accesses: 100.0,
//!     local_latency_ns: 80.0,
//!     remote_latency_ns: 140.0,
//! })
//! .expect("finite, non-negative inputs");
//! assert_eq!(cost.remote_penalty_ns, 6_000.0);
//!
//! assert_eq!(
//!     migration_break_even_accesses(12_000.0, 80.0, 140.0),
//!     Some(200.0)
//! );
//! ```

#![forbid(unsafe_code)]

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Whether a worker and an observed memory page occupy the same NUMA node.
pub enum AccessLocality {
    /// The worker and page have the same node identifier.
    Local,
    /// The worker and page have different node identifiers.
    Remote,
}

#[must_use]
/// Classifies an access from observed worker and memory-node identifiers.
///
/// The function compares identifiers only. It does not validate that either
/// node is online or allowed by the process's CPU and memory policy. Callers
/// must handle negative per-page status values from Linux `move_pages(2)`
/// before converting a page result to `u32`.
///
/// # Examples
///
/// ```
/// use numa_first_touch_migration::{AccessLocality, classify_access};
///
/// assert_eq!(classify_access(2, 2), AccessLocality::Local);
/// assert_eq!(classify_access(2, 0), AccessLocality::Remote);
/// ```
pub const fn classify_access(worker_node: u32, memory_node: u32) -> AccessLocality {
    if worker_node == memory_node {
        AccessLocality::Local
    } else {
        AccessLocality::Remote
    }
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Access counts and exposed per-access latency costs for one decision horizon.
///
/// Counts may be fractional when they are expectations or weighted workload
/// totals. Latencies must describe the same access class and measurement scope.
/// [`estimate_latency_cost`] returns `None` unless every field is finite and
/// non-negative.
pub struct LatencyInputs {
    /// Modeled local-access count during the decision horizon.
    pub local_accesses: f64,
    /// Modeled remote-access count during the decision horizon.
    pub remote_accesses: f64,
    /// Exposed, non-overlapped cost of one local access, in nanoseconds.
    pub local_latency_ns: f64,
    /// Exposed, non-overlapped cost of one remote access, in nanoseconds.
    pub remote_latency_ns: f64,
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Cost breakdown returned by [`estimate_latency_cost`], in nanoseconds.
pub struct LatencyCost {
    /// Modeled local-access cost: `local_accesses * local_latency_ns`.
    pub local_component_ns: f64,
    /// Modeled remote-access cost: `remote_accesses * remote_latency_ns`.
    pub remote_component_ns: f64,
    /// Sum of the modeled local and remote costs.
    pub total_ns: f64,
    /// Cost if every modeled access used the supplied local latency.
    pub all_local_baseline_ns: f64,
    /// Difference between `total_ns` and `all_local_baseline_ns`.
    ///
    /// This value can be negative if the supplied remote latency is lower than
    /// the supplied local latency; the function does not silently reorder them.
    pub remote_penalty_ns: f64,
}

#[must_use]
/// Adds exposed local and remote access costs.
///
/// This is an accounting identity, not a queueing or bandwidth model. It
/// predicts elapsed time only when the supplied costs are fully exposed and
/// do not overlap. Hardware NUMA distance values are relative topology hints,
/// not latency inputs to this function.
///
/// Returns `None` if an input is negative or non-finite, or if a product or sum
/// becomes non-finite.
///
/// # Examples
///
/// ```
/// use numa_first_touch_migration::{LatencyInputs, estimate_latency_cost};
///
/// let cost = estimate_latency_cost(LatencyInputs {
///     local_accesses: 3.0,
///     remote_accesses: 2.0,
///     local_latency_ns: 10.0,
///     remote_latency_ns: 25.0,
/// })
/// .expect("valid costs");
/// assert_eq!(cost.total_ns, 80.0);
/// assert_eq!(cost.all_local_baseline_ns, 50.0);
/// assert_eq!(cost.remote_penalty_ns, 30.0);
/// ```
pub fn estimate_latency_cost(inputs: LatencyInputs) -> Option<LatencyCost> {
    let values = [
        inputs.local_accesses,
        inputs.remote_accesses,
        inputs.local_latency_ns,
        inputs.remote_latency_ns,
    ];
    if !values.into_iter().all(is_non_negative_finite) {
        return None;
    }

    let local_component_ns = finite_product(inputs.local_accesses, inputs.local_latency_ns)?;
    let remote_component_ns = finite_product(inputs.remote_accesses, inputs.remote_latency_ns)?;
    let total_ns = finite_sum(local_component_ns, remote_component_ns)?;
    let total_accesses = finite_sum(inputs.local_accesses, inputs.remote_accesses)?;
    let all_local_baseline_ns = finite_product(total_accesses, inputs.local_latency_ns)?;
    let remote_penalty_ns = total_ns - all_local_baseline_ns;
    if !remote_penalty_ns.is_finite() {
        return None;
    }

    Some(LatencyCost {
        local_component_ns,
        remote_component_ns,
        total_ns,
        all_local_baseline_ns,
        remote_penalty_ns,
    })
}

#[must_use]
/// Returns the number of future accesses needed to repay one migration.
///
/// The model divides `migration_cost_ns` by
/// `remote_latency_ns - local_latency_ns`. The result can be fractional; for a
/// discrete access count, round up before using “at least break-even.” The
/// migration cost must include copying, page-table and policy work, and any
/// workload-visible disruption that belongs in the claim.
///
/// Returns `None` if an input is negative or non-finite, if remote latency is
/// not strictly greater than local latency, or if the quotient is non-finite.
/// A zero migration cost has a zero-access break-even point.
///
/// # Examples
///
/// ```
/// use numa_first_touch_migration::migration_break_even_accesses;
///
/// assert_eq!(
///     migration_break_even_accesses(1_000.0, 50.0, 100.0),
///     Some(20.0)
/// );
/// assert_eq!(migration_break_even_accesses(1_000.0, 100.0, 100.0), None);
/// ```
pub fn migration_break_even_accesses(
    migration_cost_ns: f64,
    local_latency_ns: f64,
    remote_latency_ns: f64,
) -> Option<f64> {
    if ![migration_cost_ns, local_latency_ns, remote_latency_ns]
        .into_iter()
        .all(is_non_negative_finite)
        || remote_latency_ns <= local_latency_ns
    {
        return None;
    }

    let accesses = migration_cost_ns / (remote_latency_ns - local_latency_ns);
    accesses.is_finite().then_some(accesses)
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Replication costs accumulated over one declared decision horizon.
///
/// `writes` may be fractional when it represents an expectation or weighted
/// workload total. Functions that consume this type return `None` unless every
/// field is finite and non-negative.
///
/// Capacity cost is deliberately absent because bytes and nanoseconds cannot
/// be added without a workload-specific conversion. Treat capacity as a
/// separate feasibility constraint before calling [`choose_strategy`].
pub struct ReplicationOverhead {
    /// One-time cost to create and publish the local replica, in nanoseconds.
    pub creation_cost_ns: f64,
    /// Expected writes that require replica maintenance during the horizon.
    pub writes: f64,
    /// Exposed maintenance cost per modeled write, in nanoseconds.
    pub synchronization_cost_ns_per_write: f64,
}

#[must_use]
/// Returns the remote-read count needed to repay replication overhead.
///
/// The numerator is `creation_cost_ns + writes *
/// synchronization_cost_ns_per_write`. Each read moved from remote to local
/// repays `remote_latency_ns - local_latency_ns`. Inputs must describe one
/// consistency policy and one common horizon. The result can be fractional;
/// round up when the decision requires a discrete number of reads.
///
/// Returns `None` if an input is negative or non-finite, if remote latency is
/// not strictly greater than local latency, or if an intermediate result is
/// non-finite. Zero replication overhead has a zero-read break-even point.
///
/// # Examples
///
/// ```
/// use numa_first_touch_migration::{
///     ReplicationOverhead, replication_break_even_remote_reads,
/// };
///
/// let reads = replication_break_even_remote_reads(
///     ReplicationOverhead {
///         creation_cost_ns: 800.0,
///         writes: 10.0,
///         synchronization_cost_ns_per_write: 20.0,
///     },
///     50.0,
///     100.0,
/// );
/// assert_eq!(reads, Some(20.0));
/// ```
pub fn replication_break_even_remote_reads(
    overhead: ReplicationOverhead,
    local_latency_ns: f64,
    remote_latency_ns: f64,
) -> Option<f64> {
    let overhead_ns = replication_overhead_ns(overhead)?;
    migration_break_even_accesses(overhead_ns, local_latency_ns, remote_latency_ns)
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
/// Placement strategy compared by [`choose_strategy`].
pub enum Strategy {
    /// Leave the pages remote for the modeled worker.
    KeepRemote,
    /// Move the pages to the worker's node.
    Migrate,
    /// Create a local replica while retaining another copy.
    Replicate,
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Inputs for comparing remote access, migration, and optional replication.
///
/// Costs shared by all strategies are omitted because they cancel. The model
/// assumes each access counted by `remote_accesses` becomes local after a
/// successful migration or replication. It does not model partial migration, concurrent workers,
/// bandwidth saturation, page hotness changes, or automatic NUMA balancing.
/// Access counts may be fractional when they are expectations or weighted
/// workload totals.
pub struct StrategyInputs {
    /// Accesses that remain remote if no placement action is taken.
    pub remote_accesses: f64,
    /// Exposed local access cost, in nanoseconds.
    pub local_latency_ns: f64,
    /// Exposed remote access cost, in nanoseconds.
    pub remote_latency_ns: f64,
    /// Total workload-visible cost of migrating the pages, in nanoseconds.
    pub migration_cost_ns: f64,
    /// Replication overhead, or `None` when replication is infeasible.
    pub replication: Option<ReplicationOverhead>,
}

#[derive(Clone, Copy, Debug, PartialEq)]
/// Total modeled costs and the selected strategy for one decision horizon.
///
/// Every cost field is measured in nanoseconds.
pub struct StrategyChoice {
    /// Cost of leaving every modeled access remote, in nanoseconds.
    pub keep_remote_ns: f64,
    /// Migration cost plus local cost for every modeled access, in nanoseconds.
    pub migrate_ns: f64,
    /// Replication overhead plus local access cost, or `None` when the input
    /// excludes replication.
    pub replicate_ns: Option<f64>,
    /// Lowest-cost strategy; exact ties prefer `KeepRemote` over `Migrate` over
    /// `Replicate`.
    pub selected: Strategy,
}

#[must_use]
/// Compares modeled costs for keeping, migrating, or replicating pages.
///
/// Exact ties prefer less placement state: `KeepRemote` over `Migrate`, then
/// `Migrate` over `Replicate`. Replication feasibility, capacity, consistency,
/// and failure behavior must be decided before supplying `Some(overhead)`.
///
/// Returns `None` if any numeric input, including a field inside
/// `replication: Some(...)`, is negative or non-finite, or if cost arithmetic
/// becomes non-finite.
///
/// # Examples
///
/// ```
/// use numa_first_touch_migration::{Strategy, StrategyInputs, choose_strategy};
///
/// let choice = choose_strategy(StrategyInputs {
///     remote_accesses: 1_000.0,
///     local_latency_ns: 50.0,
///     remote_latency_ns: 100.0,
///     migration_cost_ns: 10_000.0,
///     replication: None,
/// })
/// .expect("valid inputs");
/// assert_eq!(choice.selected, Strategy::Migrate);
/// ```
pub fn choose_strategy(inputs: StrategyInputs) -> Option<StrategyChoice> {
    if ![
        inputs.remote_accesses,
        inputs.local_latency_ns,
        inputs.remote_latency_ns,
        inputs.migration_cost_ns,
    ]
    .into_iter()
    .all(is_non_negative_finite)
    {
        return None;
    }

    let keep_remote_ns = finite_product(inputs.remote_accesses, inputs.remote_latency_ns)?;
    let local_access_ns = finite_product(inputs.remote_accesses, inputs.local_latency_ns)?;
    let migrate_ns = finite_sum(inputs.migration_cost_ns, local_access_ns)?;
    let replicate_ns = match inputs.replication {
        None => None,
        Some(overhead) => Some(finite_sum(
            replication_overhead_ns(overhead)?,
            local_access_ns,
        )?),
    };

    let mut selected = Strategy::KeepRemote;
    let mut lowest_ns = keep_remote_ns;
    if migrate_ns < lowest_ns {
        selected = Strategy::Migrate;
        lowest_ns = migrate_ns;
    }
    if let Some(cost) = replicate_ns
        && cost < lowest_ns
    {
        selected = Strategy::Replicate;
    }

    Some(StrategyChoice {
        keep_remote_ns,
        migrate_ns,
        replicate_ns,
        selected,
    })
}

fn replication_overhead_ns(overhead: ReplicationOverhead) -> Option<f64> {
    if ![
        overhead.creation_cost_ns,
        overhead.writes,
        overhead.synchronization_cost_ns_per_write,
    ]
    .into_iter()
    .all(is_non_negative_finite)
    {
        return None;
    }

    let maintenance_ns =
        finite_product(overhead.writes, overhead.synchronization_cost_ns_per_write)?;
    finite_sum(overhead.creation_cost_ns, maintenance_ns)
}

fn is_non_negative_finite(value: f64) -> bool {
    value.is_finite() && value >= 0.0
}

fn finite_product(left: f64, right: f64) -> Option<f64> {
    let product = left * right;
    product.is_finite().then_some(product)
}

fn finite_sum(left: f64, right: f64) -> Option<f64> {
    let sum = left + right;
    sum.is_finite().then_some(sum)
}

#[cfg(test)]
mod tests {
    use super::{
        AccessLocality, LatencyInputs, ReplicationOverhead, Strategy, StrategyInputs,
        choose_strategy, classify_access, estimate_latency_cost, migration_break_even_accesses,
        replication_break_even_remote_reads,
    };

    #[test]
    fn locality_is_identifier_equality() {
        assert_eq!(classify_access(0, 0), AccessLocality::Local);
        assert_eq!(classify_access(0, 1), AccessLocality::Remote);
    }

    #[test]
    fn latency_cost_preserves_components() {
        let cost = estimate_latency_cost(LatencyInputs {
            local_accesses: 4.0,
            remote_accesses: 2.0,
            local_latency_ns: 10.0,
            remote_latency_ns: 25.0,
        })
        .expect("valid cost model");

        assert_eq!(cost.local_component_ns, 40.0);
        assert_eq!(cost.remote_component_ns, 50.0);
        assert_eq!(cost.total_ns, 90.0);
        assert_eq!(cost.all_local_baseline_ns, 60.0);
        assert_eq!(cost.remote_penalty_ns, 30.0);
    }

    #[test]
    fn latency_cost_rejects_invalid_inputs_and_overflow() {
        assert_eq!(
            estimate_latency_cost(LatencyInputs {
                local_accesses: -1.0,
                remote_accesses: 0.0,
                local_latency_ns: 1.0,
                remote_latency_ns: 1.0,
            }),
            None
        );
        assert_eq!(
            estimate_latency_cost(LatencyInputs {
                local_accesses: f64::MAX,
                remote_accesses: 0.0,
                local_latency_ns: 2.0,
                remote_latency_ns: 2.0,
            }),
            None
        );
    }

    #[test]
    fn migration_break_even_uses_remote_increment() {
        assert_eq!(
            migration_break_even_accesses(2_000.0, 50.0, 150.0),
            Some(20.0)
        );
        assert_eq!(migration_break_even_accesses(0.0, 50.0, 150.0), Some(0.0));
        assert_eq!(migration_break_even_accesses(2_000.0, 150.0, 150.0), None);
        assert_eq!(migration_break_even_accesses(2_000.0, 151.0, 150.0), None);
    }

    #[test]
    fn replication_break_even_includes_write_maintenance() {
        let overhead = ReplicationOverhead {
            creation_cost_ns: 1_000.0,
            writes: 10.0,
            synchronization_cost_ns_per_write: 50.0,
        };
        assert_eq!(
            replication_break_even_remote_reads(overhead, 50.0, 100.0),
            Some(30.0)
        );
    }

    #[test]
    fn strategy_can_keep_migrate_or_replicate() {
        let base = StrategyInputs {
            remote_accesses: 100.0,
            local_latency_ns: 10.0,
            remote_latency_ns: 20.0,
            migration_cost_ns: 2_000.0,
            replication: None,
        };
        assert_eq!(
            choose_strategy(base).expect("valid keep model").selected,
            Strategy::KeepRemote
        );

        let migrate = StrategyInputs {
            migration_cost_ns: 500.0,
            ..base
        };
        assert_eq!(
            choose_strategy(migrate)
                .expect("valid migration model")
                .selected,
            Strategy::Migrate
        );

        let replicate = StrategyInputs {
            migration_cost_ns: 900.0,
            replication: Some(ReplicationOverhead {
                creation_cost_ns: 200.0,
                writes: 2.0,
                synchronization_cost_ns_per_write: 50.0,
            }),
            ..base
        };
        assert_eq!(
            choose_strategy(replicate)
                .expect("valid replication model")
                .selected,
            Strategy::Replicate
        );
    }

    #[test]
    fn strategy_ties_prefer_less_placement_state() {
        let choice = choose_strategy(StrategyInputs {
            remote_accesses: 100.0,
            local_latency_ns: 10.0,
            remote_latency_ns: 20.0,
            migration_cost_ns: 1_000.0,
            replication: Some(ReplicationOverhead {
                creation_cost_ns: 1_000.0,
                writes: 0.0,
                synchronization_cost_ns_per_write: 0.0,
            }),
        })
        .expect("valid tie model");

        assert_eq!(choice.keep_remote_ns, choice.migrate_ns);
        assert_eq!(choice.replicate_ns, Some(choice.migrate_ns));
        assert_eq!(choice.selected, Strategy::KeepRemote);
    }
}
