//! Model a preempted counter update and its restart contract.
//!
//! Native Linux execution lives in `experiment/counter.c` and `counter.S`.
//! The model assumes the tentative value stays private until the commit store.
//!
//! ```
//! use restartable_sequences::interrupted;
//! assert_eq!(interrupted([10, 0], 0, 1, 1, true), [11, 1]);
//! ```

/// Apply one interrupted update plus `intervening` updates on its original CPU.
///
/// With `restart`, the interrupted operation recomputes on `resumed_cpu`.
/// Otherwise it writes the stale value to the original slot.
///
/// # Panics
/// Panics for an out-of-range CPU or counter overflow.
pub fn interrupted(
    mut slots: [u64; 2],
    original_cpu: usize,
    resumed_cpu: usize,
    intervening: u64,
    restart: bool,
) -> [u64; 2] {
    assert!(original_cpu < 2 && resumed_cpu < 2);
    let tentative = slots[original_cpu].checked_add(1).unwrap();
    slots[original_cpu] = slots[original_cpu].checked_add(intervening).unwrap();
    if restart {
        slots[resumed_cpu] = slots[resumed_cpu].checked_add(1).unwrap();
    } else {
        slots[original_cpu] = tentative;
    }
    slots
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restart_matches_serial_event_oracle() {
        for a in 0..16 {
            for b in 0..16 {
                for original in 0..2 {
                    for resumed in 0..2 {
                        for other in 0..16 {
                            let mut oracle = [a, b];
                            let mut events = vec![original; other as usize];
                            events.push(resumed);
                            for cpu in events {
                                oracle[cpu] += 1;
                            }
                            assert_eq!(interrupted([a, b], original, resumed, other, true), oracle);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn same_cpu_preemption_also_loses_updates() {
        assert_eq!(interrupted([10, 0], 0, 0, 1, false), [11, 0]);
        assert_eq!(interrupted([10, 0], 0, 0, 1, true), [12, 0]);
    }
}
