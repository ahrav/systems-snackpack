//! Discrete autoscaler with fixed measurement and actuation delays.
//!
//! One tick is ten seconds. Each ready replica serves 1,000 requests per tick.
//! Commands target 600 arrivals per replica and remain within 1..=40 replicas.
//! The retained command uses units of 1/4,800 replicas, preserving exact updates.
//!
//! ```
//! use feedback_control::{simulate, Policy};
//! let rows = simulate(&[6_000; 20], &[true; 20], Policy::Slow, 2, 3);
//! assert!(rows.iter().all(|r| r.ready == 10 && r.queue == 0));
//! ```

use std::collections::VecDeque;

/// Capacity update rule.
#[derive(Clone, Copy, Debug)]
pub enum Policy {
    /// Accumulate the entire observed capacity deficit.
    Fast,
    /// Accumulate one eighth of the observed capacity deficit.
    Slow,
    /// Set capacity from observed offered arrivals and the throughput model.
    FeedForward,
}

/// State after a tick's arrivals, service, observation, and recommendation.
#[derive(Debug, PartialEq, Eq)]
pub struct Row {
    /// Ready replicas serving this interval.
    pub ready: i64,
    /// Retained desired capacity in units of 1/4,800 replicas.
    pub desired: i64,
    /// Rounded absolute command, effective after the configured actuation delay.
    pub command: i64,
    /// Unserved requests after service in this interval.
    pub queue: i64,
}

/// Replay a finite demand trace with prehistory of ten replicas and 6,000 arrivals.
///
/// `valid[k]` marks whether the measurement produced at tick k is usable. An
/// unavailable observation holds the desired value. Absolute commands take effect
/// in order; every command replaces ready capacity after `actuation_delay` ticks.
/// Both scaling directions have the same delay. Saturation clamps retained state.
///
/// # Panics
/// Panics for mismatched lengths, zero actuation delay, delays above 1,000,
/// more than one million ticks, or arrivals outside 0..=1,000,000 per tick.
pub fn simulate(
    arrivals: &[i64],
    valid: &[bool],
    policy: Policy,
    measurement_delay: usize,
    actuation_delay: usize,
) -> Vec<Row> {
    assert_eq!(arrivals.len(), valid.len());
    assert!((1..=1_000).contains(&actuation_delay));
    assert!(measurement_delay <= 1_000 && arrivals.len() <= 1_000_000);
    assert!(arrivals.iter().all(|a| (0..=1_000_000).contains(a)));
    let mut pending = VecDeque::from(vec![10; actuation_delay]);
    let mut observed = VecDeque::from(vec![(6_000, 10, true); measurement_delay]);
    let mut desired = 48_000;
    let mut queue = 0;
    let mut rows = Vec::with_capacity(arrivals.len());
    for (&arrival, &usable) in arrivals.iter().zip(valid) {
        let ready = pending.pop_front().unwrap();
        queue = (queue + arrival - 1_000 * ready).max(0);
        observed.push_back((arrival, ready, usable));
        let (load, measured_ready, available) = observed.pop_front().unwrap();
        if available {
            let deficit = load - 600 * measured_ready;
            desired = match policy {
                Policy::Fast => desired + 8 * deficit,
                Policy::Slow => desired + deficit,
                Policy::FeedForward => 8 * load,
            }
            .clamp(4_800, 40 * 4_800);
        }
        let command = (desired + 4_799) / 4_800;
        pending.push_back(command);
        rows.push(Row {
            ready,
            desired,
            command,
            queue,
        });
    }
    rows
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_becomes_ready_at_declared_tick() {
        let rows = simulate(&[12_000; 10], &[true; 10], Policy::FeedForward, 2, 3);
        assert!(rows[..5].iter().all(|r| r.ready == 10));
        assert_eq!(rows[5].ready, 20);
        assert_eq!(rows[4].queue, 10_000);
        assert_eq!(rows[6].queue, 0);
    }

    #[test]
    fn missing_samples_hold_state_and_saturation_releases() {
        let rows = simulate(
            &[60_000, 0, 6_000, 6_000],
            &[true, false, true, true],
            Policy::FeedForward,
            0,
            1,
        );
        assert_eq!(rows[0].command, 40);
        assert_eq!(rows[1].command, 40);
        assert_eq!(rows[2].command, 10);
        assert_eq!(rows[3].ready, 10);
    }

    #[test]
    fn gain_policies_accumulate_fractional_deficits_and_clamp_low() {
        // 6,300 arrivals against ten ready replicas is a deficit of half a replica.
        let fast = simulate(&[6_300; 2], &[true; 2], Policy::Fast, 0, 1);
        assert_eq!((fast[0].desired, fast[0].command), (50_400, 11));
        assert_eq!(
            (fast[1].ready, fast[1].desired, fast[1].command),
            (11, 48_000, 10)
        );
        let slow = simulate(&[6_300; 2], &[true; 2], Policy::Slow, 0, 1);
        assert_eq!((slow[0].desired, slow[0].command), (48_300, 11));
        assert_eq!(
            (slow[1].ready, slow[1].desired, slow[1].command),
            (11, 48_000, 10)
        );
        let idle = simulate(&[0], &[true], Policy::Fast, 0, 1);
        assert_eq!((idle[0].desired, idle[0].command), (4_800, 1));
    }

    #[test]
    fn delay_free_linear_recurrence_matches_closed_form() {
        let mut error = 1.0_f64;
        for k in 0..100 {
            assert!((error - 0.875_f64.powi(k)).abs() < 1e-14);
            error -= error / 8.0;
        }
    }
}
