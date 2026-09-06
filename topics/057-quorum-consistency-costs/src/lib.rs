//! Deterministic fixed-membership quorum examples, not a network implementation.
//!
//! Tags stand for single-writer versions; values are omitted. Replicas never
//! forget a tag. A selected set represents replies already received by the
//! caller, not a claim that messages were sent atomically to that set.
//!
//! ```
//! use quorum_consistency_costs::{publish, read};
//! let mut replicas = [1, 0, 0];
//! assert_eq!(read(&replicas, 0b011), Some(1));
//! assert_eq!(read(&replicas, 0b110), Some(0));
//! assert!(publish(&mut replicas, 0b110, 1));
//! assert_eq!(read(&replicas, 0b110), Some(1));
//! ```

/// Retain the newer single-writer tag when messages arrive out of order.
///
/// Distinct tags identify distinct writes. This does not allocate tags or model
/// restart persistence. The non-inlined function is a code-generation probe.
#[inline(never)]
pub fn retain_tag(stored: u64, incoming: u64) -> u64 {
    stored.max(incoming)
}

fn valid_set(len: usize, mask: u16) -> bool {
    (1..=15).contains(&len) && mask != 0 && mask < (1u16 << len)
}

/// Return the largest tag in a nonempty response set, or `None` for an invalid set.
///
/// Bit `i` selects replica `i`. At most 15 replicas are supported. This models
/// query replies only: returning this result does not perform read write-back.
pub fn read(replicas: &[u64], mask: u16) -> Option<u64> {
    if !valid_set(replicas.len(), mask) {
        return None;
    }
    replicas
        .iter()
        .enumerate()
        .filter(|(i, _)| mask & (1 << i) != 0)
        .map(|(_, tag)| *tag)
        .max()
}

/// Deliver a tag to a nonempty selected set, retaining higher existing tags.
///
/// Return `false` without mutation for an invalid set. Completion represents
/// selected acknowledgments; this function does not simulate disk persistence.
pub fn publish(replicas: &mut [u64], mask: u16, tag: u64) -> bool {
    if !valid_set(replicas.len(), mask) {
        return false;
    }
    for (i, stored) in replicas.iter_mut().enumerate() {
        if mask & (1 << i) != 0 {
            *stored = retain_tag(*stored, tag);
        }
    }
    true
}

/// Enumerate all sets containing exactly `size` members among `replicas`.
///
/// Invalid sizes and replica counts outside 1..=15 return an empty vector.
pub fn sets(replicas: usize, size: u32) -> Vec<u16> {
    if !(1..=15).contains(&replicas) || size == 0 || size > replicas as u32 {
        return Vec::new();
    }
    (1..(1u16 << replicas))
        .filter(|mask| mask.count_ones() == size)
        .collect()
}

/// Compute one phase's modeled nanoseconds from successful response times.
///
/// `required` is one-based. Missing responses are omitted. Return `None` if too
/// few replies exist, the threshold is zero, or adding coordinator cost overflows.
/// These inputs are hypothetical completion times, not measured network samples.
pub fn phase_ns(responses: &[u64], required: usize, coordinator_ns: u64) -> Option<u64> {
    if required == 0 || required > responses.len() {
        return None;
    }
    let mut sorted = responses.to_vec();
    sorted.sort_unstable();
    sorted[required - 1].checked_add(coordinator_ns)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn incomplete_write_allows_read_inversion() {
        let replicas = [1, 0, 0];
        assert_eq!(read(&replicas, 0b011), Some(1));
        assert_eq!(read(&replicas, 0b110), Some(0));
    }

    #[test]
    fn strict_overlap_matches_all_sets_through_seven_replicas() {
        for n in 1..=7 {
            for r in 1..=n as u32 {
                for w in 1..=n as u32 {
                    let all_intersect = sets(n, r)
                        .iter()
                        .all(|read| sets(n, w).iter().all(|write| read & write != 0));
                    assert_eq!(all_intersect, r + w > n as u32);
                }
            }
        }
    }

    #[test]
    fn completed_write_is_visible_to_every_intersecting_read() {
        for n in [3, 5, 7] {
            let majority = (n / 2 + 1) as u32;
            for write in sets(n, majority) {
                let mut replicas = vec![0; n];
                assert!(publish(&mut replicas, write, 1));
                for query in sets(n, majority) {
                    assert_eq!(read(&replicas, query), Some(1));
                }
            }
        }
    }

    #[test]
    fn write_back_protects_every_later_majority() {
        for n in [3, 5, 7] {
            let majority = (n / 2 + 1) as u32;
            for exposed in 0..n {
                let mut partial = vec![0; n];
                partial[exposed] = 1;
                for query in sets(n, majority) {
                    let observed = read(&partial, query).unwrap();
                    for write_back in sets(n, majority) {
                        let mut replicas = partial.clone();
                        assert!(publish(&mut replicas, write_back, observed));
                        for later in sets(n, majority) {
                            assert!(read(&replicas, later).unwrap() >= observed);
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn no_write_control_stays_at_zero() {
        for query in sets(3, 2) {
            assert_eq!(read(&[0, 0, 0], query), Some(0));
        }
    }

    #[test]
    fn delayed_older_message_cannot_erase_newer_tag() {
        let mut replicas = [2, 1, 0];
        assert!(publish(&mut replicas, 0b111, 1));
        assert_eq!(replicas, [2, 1, 1]);
    }

    #[test]
    fn sloppy_sets_use_a_different_universe() {
        // A, B, C are home replicas; D is a fallback.
        let mut replicas = [0; 4];
        assert!(publish(&mut replicas, 0b1001, 1)); // A, D
        assert_eq!(read(&replicas, 0b0110), Some(0)); // B, C
    }

    #[test]
    fn invalid_sets_never_mutate() {
        let mut replicas = [0; 3];
        for mask in [0, 0b1000, u16::MAX] {
            assert_eq!(read(&replicas, mask), None);
            assert!(!publish(&mut replicas, mask, 1));
            assert_eq!(replicas, [0; 3]);
        }
        assert_eq!(read(&[], 1), None);
        assert_eq!(read(&[0; 16], 1), None);
        assert!(sets(16, 2).is_empty());
        assert!(sets(3, 0).is_empty());
        assert!(sets(3, 4).is_empty());
    }

    #[test]
    fn phase_cost_uses_threshold_and_reachable_responses() {
        assert_eq!(
            phase_ns(&[20_000_000, 1_000_000, 4_000_000], 2, 200_000),
            Some(4_200_000)
        );
        assert_eq!(
            phase_ns(&[1_000_000, 20_000_000], 2, 200_000),
            Some(20_200_000)
        );
        assert_eq!(phase_ns(&[1_000_000], 2, 200_000), None);
        assert_eq!(phase_ns(&[1], 0, 0), None);
        assert_eq!(phase_ns(&[u64::MAX], 1, 1), None);
    }
}
