//! Finite load-selection models with explicit observations and admission limits.
//!
//! Counts are unfinished equal-work requests. There are no departures, network
//! effects, random generators, shared-client counters, or wall-clock measurements.
//! Candidate indices are positions in an already eligible snapshot.
//!
//! ```
//! use topic062_load_balancing::{least, two_choice};
//! let snapshot = [0, 1, 1, 1];
//! assert_eq!(least(&snapshot), Some(0));
//! assert_eq!(two_choice(&snapshot, 1, 1), Some(1));
//! ```

/// Return the first minimum, or `None` for an empty eligible snapshot.
///
/// This deterministic tie rule belongs to this model, not to every proxy.
#[inline(never)]
pub fn least(snapshot: &[u32]) -> Option<usize> {
    snapshot
        .iter()
        .enumerate()
        .min_by_key(|(_, q)| *q)
        .map(|(i, _)| i)
}

/// Compare two supplied positions, retaining the first on a tie.
///
/// Duplicate positions model sampling with replacement. Invalid positions return
/// `None`; this function neither generates random choices nor repairs bad input.
#[inline(never)]
pub fn two_choice(snapshot: &[u32], a: usize, b: usize) -> Option<usize> {
    let qa = snapshot.get(a)?;
    let qb = snapshot.get(b)?;
    Some(if qb < qa { b } else { a })
}

/// Select and reserve one request under a per-endpoint outstanding limit.
///
/// This is one serialized model transition. It is not a concurrent admission
/// protocol. Rejection leaves counts unchanged. Completion accounting, backend
/// cancellation, and release-once tokens are outside this model.
///
/// # Panics
/// Panics if the eligibility mask and count slice have different lengths.
pub fn reserve_least(counts: &mut [u32], eligible: &[bool], limit: u32) -> Option<usize> {
    assert_eq!(counts.len(), eligible.len());
    let chosen = counts
        .iter()
        .enumerate()
        .filter(|(i, q)| eligible[*i] && **q < limit)
        .min_by_key(|(_, q)| *q)
        .map(|(i, _)| i)?;
    counts[chosen] += 1;
    Some(chosen)
}

/// Choose the first minimum of `(unfinished + 1) / capacity` without floats.
///
/// Capacity is positive integer standard requests per model time unit. Zero
/// capacity excludes a server. The model assumes serial equal-work service.
/// Cross-products fit `u64` for these `u32` inputs, including `u32::MAX` counts.
///
/// # Panics
/// Panics if count and capacity slices have different lengths.
#[inline(never)]
pub fn shortest_completion(counts: &[u32], capacities: &[u32]) -> Option<usize> {
    assert_eq!(counts.len(), capacities.len());
    let mut best: Option<usize> = None;
    for (i, &capacity) in capacities.iter().enumerate() {
        if capacity == 0 {
            continue;
        }
        if best.is_none_or(|j| {
            (u64::from(counts[i]) + 1) * u64::from(capacities[j])
                < (u64::from(counts[j]) + 1) * u64::from(capacity)
        }) {
            best = Some(i);
        }
    }
    best
}

/// Return the exact running-example results after 16 arrivals with no departures.
///
/// The tuple contains stale full scan, current local reservations, and one use
/// of every ordered candidate pair against the unchanged snapshot, respectively.
pub fn burst_example() -> ([u32; 4], [u32; 4], [u32; 4]) {
    let snapshot = [0, 1, 1, 1];
    let mut stale = snapshot;
    let mut reserved = snapshot;
    let mut pairs = snapshot;
    for _ in 0..16 {
        stale[least(&snapshot).unwrap()] += 1;
        reserve_least(&mut reserved, &[true; 4], u32::MAX).unwrap();
    }
    for a in 0..4 {
        for b in 0..4 {
            pairs[two_choice(&snapshot, a, b).unwrap()] += 1;
        }
    }
    (stale, reserved, pairs)
}

/// Integer model time units needed to drain a batch, rounded up per server.
///
/// All work is available at time zero. Each server processes its assigned work
/// at its fixed capacity. Zero capacity with nonzero work returns `None`.
/// An empty fleet or zero-work batch drains in zero time units.
///
/// # Panics
/// Panics if batch and capacity slices have different lengths.
pub fn drain_time(batch: &[u32], capacities: &[u32]) -> Option<u64> {
    assert_eq!(batch.len(), capacities.len());
    let mut maximum = 0;
    for (&count, &capacity) in batch.iter().zip(capacities) {
        if count == 0 {
            continue;
        }
        if capacity == 0 {
            return None;
        }
        maximum = maximum.max(u64::from(count).div_ceil(u64::from(capacity)));
    }
    Some(maximum)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn unique_stale_minimum_herds_without_a_tie() {
        let (stale, reserved, pairs) = burst_example();
        assert_eq!(stale, [16, 1, 1, 1]);
        assert_eq!(reserved, [5, 5, 5, 4]);
        assert_eq!(pairs, [7, 4, 4, 4]);
        for result in [stale, reserved, pairs] {
            assert_eq!(result.iter().sum::<u32>(), 19);
        }
    }

    #[test]
    fn two_hosts_can_sample_busy_twice() {
        let snapshot = [0, 1];
        let busy = (0..2)
            .flat_map(|a| (0..2).map(move |b| (a, b)))
            .filter(|&(a, b)| two_choice(&snapshot, a, b) == Some(1))
            .count();
        assert_eq!(busy, 1); // One of four equally likely ordered pairs.
    }

    #[test]
    fn pair_comparison_exhaustive_small_domain() {
        for x in 0..4 {
            for y in 0..4 {
                for z in 0..4 {
                    let q = [x, y, z];
                    for a in 0..3 {
                        for b in 0..3 {
                            let selected = two_choice(&q, a, b).unwrap();
                            assert_eq!(q[selected], q[a].min(q[b]));
                            if q[a] == q[b] {
                                assert_eq!(selected, a);
                            }
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn empty_and_invalid_candidates_are_explicit() {
        assert_eq!(least(&[]), None);
        assert_eq!(two_choice(&[], 0, 0), None);
        assert_eq!(two_choice(&[0], 0, 1), None);
        assert_eq!(two_choice(&[0], 0, 0), Some(0));
    }

    #[test]
    fn reservations_respect_health_and_limits() {
        let mut q = [0, 1, 2];
        assert_eq!(reserve_least(&mut q, &[false, true, true], 2), Some(1));
        assert_eq!(q, [0, 2, 2]);
        assert_eq!(reserve_least(&mut q, &[false, true, true], 2), None);
        assert_eq!(q, [0, 2, 2]);
        assert_eq!(reserve_least(&mut q, &[true; 3], 0), None);
        assert_eq!(q, [0, 2, 2]);
    }

    #[test]
    fn saturation_cannot_wrap_counts() {
        let mut q = [u32::MAX];
        assert_eq!(reserve_least(&mut q, &[true], u32::MAX), None);
        assert_eq!(q, [u32::MAX]);
        assert_eq!(shortest_completion(&q, &[u32::MAX]), Some(0));
        assert_eq!(shortest_completion(&[u32::MAX, 0], &[u32::MAX, 1]), Some(1));
    }

    #[test]
    fn count_and_completion_time_can_disagree() {
        assert_eq!(least(&[3, 0]), Some(1));
        assert_eq!(shortest_completion(&[3, 0], &[4, 1]), Some(0)); // Exact tie.
        assert_eq!(shortest_completion(&[2, 0], &[4, 1]), Some(0)); // Fast server wins.
        assert_eq!(shortest_completion(&[0, 0], &[0, 0]), None);
    }

    #[test]
    fn equal_initial_load_control_is_balanced_with_reservations() {
        let mut q = [0; 4];
        for _ in 0..16 {
            reserve_least(&mut q, &[true; 4], u32::MAX).unwrap();
        }
        assert_eq!(q, [4; 4]);
    }

    #[test]
    fn weighted_batch_uses_heterogeneous_capacity() {
        let capacities = [4, 4, 1, 1];
        assert_eq!(drain_time(&[10, 10, 10, 10], &capacities), Some(10));
        assert_eq!(drain_time(&[16, 16, 4, 4], &capacities), Some(4));
        assert_eq!(drain_time(&[1], &[0]), None);
        assert_eq!(drain_time(&[0], &[0]), Some(0));
        assert_eq!(drain_time(&[], &[]), Some(0));
    }

    #[test]
    #[should_panic]
    fn malformed_mask_rejects_setup() {
        reserve_least(&mut [0], &[], 1);
    }
}
