//! Accelerator offload cost models and two exact CPU baselines.
//!
//! Times in the scheduling model are caller-supplied assumptions. Three
//! independent engines process H2D, compute, and D2H in that order. A buffer
//! slot is held through D2H completion. Jobs and engines preserve FIFO order.
//! Run `cargo run -p accelerator-offload --release -- model-grid` for model cases.
//!
//! ```
//! use accelerator_offload::schedule;
//! let batches = schedule(8, 3, [4, 2, 4]).unwrap();
//! assert_eq!(batches.last().unwrap().end[2], 38);
//! ```

/// Start and completion times for one batch's three stages.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Batch {
    /// Stage start times: H2D, compute, D2H.
    pub start: [u64; 3],
    /// Stage completion times in the same order.
    pub end: [u64; 3],
}

/// Schedule ready batches on independent FIFO engines and reusable buffer slots.
///
/// Durations may be zero. Returns an error for zero slots or time overflow.
/// Launch, allocation, host preparation, and arrival delays are outside this model.
pub fn schedule(
    jobs: usize,
    slots: usize,
    durations: [u64; 3],
) -> Result<Vec<Batch>, &'static str> {
    if slots == 0 {
        return Err("at least one buffer slot is required");
    }
    let mut engines = [0; 3];
    let mut reusable = vec![0; slots.min(jobs)];
    let mut result = Vec::with_capacity(jobs);
    for job in 0..jobs {
        let mut ready = reusable[job % slots];
        let mut batch = Batch {
            start: [0; 3],
            end: [0; 3],
        };
        for stage in 0..3 {
            batch.start[stage] = ready.max(engines[stage]);
            ready = batch.start[stage]
                .checked_add(durations[stage])
                .ok_or("time overflow")?;
            batch.end[stage] = ready;
            engines[stage] = ready;
        }
        reusable[job % slots] = ready;
        result.push(batch);
    }
    Ok(result)
}

/// One exact unsigned 32-bit transform, with modular multiplication and addition.
pub fn step(x: u32) -> u32 {
    (x ^ (x >> 13))
        .wrapping_mul(1_664_525)
        .wrapping_add(1_013_904_223)
}

/// Complete all rounds of each element before advancing to the next element.
///
/// Panics when the input and output lengths differ.
#[inline(never)]
pub fn element_major(input: &[u32], output: &mut [u32], rounds: u32) {
    assert_eq!(input.len(), output.len());
    for (&value, dest) in input.iter().zip(output) {
        let mut value = value;
        for _ in 0..rounds {
            value = step(value);
        }
        *dest = value;
    }
}

/// Scan all elements for each round, retaining intermediate values in the output.
///
/// Panics when the input and output lengths differ.
#[inline(never)]
pub fn round_major(input: &[u32], output: &mut [u32], rounds: u32) {
    output.copy_from_slice(input);
    for _ in 0..rounds {
        for value in output.iter_mut() {
            *value = step(*value);
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn slot_capacity_changes_overlap() {
        for (slots, total) in [(1, 80), (2, 44), (3, 38)] {
            assert_eq!(schedule(8, slots, [4, 2, 4]).unwrap()[7].end[2], total);
        }
    }

    #[test]
    fn preserves_dependencies_engines_and_slot_lifetimes() {
        for slots in 1..=4 {
            for h in 0..=4 {
                for k in 0..=4 {
                    for d in 0..=4 {
                        let times = [h, k, d];
                        let batches = schedule(9, slots, times).unwrap();
                        for (j, batch) in batches.iter().enumerate() {
                            for (stage, duration) in times.iter().enumerate() {
                                assert_eq!(batch.end[stage] - batch.start[stage], *duration);
                                if stage > 0 {
                                    assert!(batch.start[stage] >= batch.end[stage - 1]);
                                }
                                if j > 0 {
                                    assert!(batch.start[stage] >= batches[j - 1].end[stage]);
                                }
                            }
                            if j >= slots {
                                assert!(batch.start[0] >= batches[j - slots].end[2]);
                            }
                        }
                    }
                }
            }
        }
    }

    #[test]
    fn enough_slots_reaches_pipeline_formula() {
        for h in 0..=4 {
            for k in 0..=4 {
                for d in 0..=4 {
                    let last = schedule(9, 9, [h, k, d]).unwrap()[8].end[2];
                    assert_eq!(last, h + k + d + 8 * h.max(k).max(d));
                }
            }
        }
    }

    #[test]
    fn boundary_and_overflow_contracts() {
        assert!(schedule(0, 1, [0; 3]).unwrap().is_empty());
        assert!(schedule(1, 0, [1; 3]).is_err());
        assert!(schedule(1, 1, [u64::MAX, 1, 0]).is_err());
        assert_eq!(
            schedule(1, 1, [u64::MAX, 0, 0]).unwrap()[0].end[2],
            u64::MAX
        );
    }

    #[test]
    fn transforms_preserve_zero_rounds_and_agree() {
        let input = [0, 1, u32::MAX, 0x12345678, 0x80000000];
        let mut a = [0; 5];
        let mut b = [0; 5];
        element_major(&input, &mut a, 0);
        assert_eq!(input, a);
        assert_eq!(step(0), 1_013_904_223);
        for rounds in [0, 1, 2, 31, 32] {
            element_major(&input, &mut a, rounds);
            round_major(&input, &mut b, rounds);
            assert_eq!(a, b);
        }
    }
}
