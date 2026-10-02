//! Scan granularity and morsel coverage, with an explicit wrapping-sum contract.
//!
//! This is not a SQL engine. Zero survivors return zero; amounts sum modulo 2^64.
//! Generated benchmark inputs cannot overflow. No allocation occurs inside the
//! timed scan kernels except the reusable selection buffer at batch entry.
//!
//! ```
//! use topic065_query_execution::{Columns, batched, fused, morsels};
//! let data = Columns::new(vec![0, 1, 0], vec![10, 20, 30], vec![1, 1, 0]);
//! assert_eq!(fused(&data, 1), 10);
//! assert_eq!(batched(&data, 1, 2), 10);
//! assert_eq!(morsels(&data, 1, 2, 2), 10);
//! ```

use std::hint::black_box;
use std::ops::Range;
use std::sync::atomic::{AtomicUsize, Ordering};

/// Equal-length region, amount, and validity columns.
pub struct Columns {
    region: Vec<u8>,
    amount: Vec<u64>,
    valid: Vec<u8>,
}

impl Columns {
    /// Construct columns; panic for unequal lengths or validity outside 0..=1.
    pub fn new(region: Vec<u8>, amount: Vec<u64>, valid: Vec<u8>) -> Self {
        assert_eq!(region.len(), amount.len());
        assert_eq!(region.len(), valid.len());
        assert!(valid.iter().all(|&v| v <= 1));
        Self {
            region,
            amount,
            valid,
        }
    }

    /// Deterministic scrambled regions, bounded amounts, and every 17th row null.
    pub fn generated(n: usize) -> Self {
        let mut x = 42_u64;
        let mut region = Vec::with_capacity(n);
        let mut amount = Vec::with_capacity(n);
        let mut valid = Vec::with_capacity(n);
        for i in 0..n {
            x = x
                .wrapping_mul(6364136223846793005)
                .wrapping_add(1442695040888963407);
            region.push((x >> 32) as u8);
            amount.push(1 + (x >> 40) % 1000);
            valid.push(u8::from(i % 17 != 0));
        }
        Self::new(region, amount, valid)
    }

    /// Number of input rows.
    pub fn len(&self) -> usize {
        self.region.len()
    }

    /// Whether no input rows exist.
    pub fn is_empty(&self) -> bool {
        self.region.is_empty()
    }

    /// Independent iterator formulation of the wrapping sum for correctness.
    pub fn oracle(&self, mask: u8) -> u64 {
        self.region
            .iter()
            .zip(&self.amount)
            .zip(&self.valid)
            .filter(|&((&region, _), &valid)| region & mask == 0 && valid == 1)
            .fold(0_u64, |sum, ((_, &amount), _)| sum.wrapping_add(amount))
    }
}

#[inline(never)]
fn row(data: &Columns, i: usize, mask: u8) -> u64 {
    if data.region[i] & mask == 0 && data.valid[i] == 1 {
        data.amount[i]
    } else {
        0
    }
}

/// One deliberately opaque indirect function call per input row.
///
/// This models a dispatch boundary, not the full Volcano iterator protocol.
#[inline(never)]
pub fn dispatched(data: &Columns, mask: u8) -> u64 {
    let call = black_box(row as fn(&Columns, usize, u8) -> u64);
    let mut sum = 0_u64;
    for i in 0..data.len() {
        sum = sum.wrapping_add(call(data, i, mask));
    }
    sum
}

#[inline(never)]
fn batch(data: &Columns, range: Range<usize>, mask: u8, selected: &mut Vec<usize>) -> u64 {
    selected.clear();
    for i in range {
        if data.region[i] & mask == 0 && data.valid[i] == 1 {
            selected.push(i);
        }
    }
    let mut sum = 0_u64;
    for &i in selected.iter() {
        sum = sum.wrapping_add(data.amount[i]);
    }
    sum
}

/// Select positions, then aggregate, with one opaque call per batch.
///
/// The buffer is allocated once per query invocation and reused across batches.
/// Positions are native `usize`, unlike the lesson's illustrative four-byte model.
/// Panic if `size` is zero. Huge sizes reserve at most the input length.
#[inline(never)]
pub fn batched(data: &Columns, mask: u8, size: usize) -> u64 {
    assert!(size > 0);
    let mut selected = Vec::with_capacity(size.min(data.len()));
    let call = black_box(batch as fn(&Columns, Range<usize>, u8, &mut Vec<usize>) -> u64);
    let mut sum = 0_u64;
    for start in (0..data.len()).step_by(size) {
        let end = start + size.min(data.len() - start);
        sum = sum.wrapping_add(call(data, start..end, mask, &mut selected));
    }
    sum
}

#[inline(never)]
fn fused_range(data: &Columns, range: Range<usize>, mask: u8) -> u64 {
    let mut sum = 0_u64;
    for i in range {
        if data.region[i] & mask == 0 && data.valid[i] == 1 {
            sum = sum.wrapping_add(data.amount[i]);
        }
    }
    sum
}

/// One scan loop with no intermediate selection positions.
#[inline(never)]
pub fn fused(data: &Columns, mask: u8) -> u64 {
    fused_range(data, 0..data.len(), mask)
}

fn claim(next: &AtomicUsize, len: usize, size: usize) -> Option<Range<usize>> {
    assert!(size > 0);
    next.fetch_update(Ordering::Relaxed, Ordering::Relaxed, |start| {
        (start < len).then(|| start + size.min(len - start))
    })
    .ok()
    .map(|start| start..start + size.min(len - start))
}

/// Claim disjoint morsels and join all workers before reducing private sums.
///
/// Relaxed atomics allocate indexes only. Immutable inputs exist before spawning;
/// thread joins synchronize completion. An exhausted allocator alone is not a
/// completion barrier. This is not a NUMA-aware or persistent worker-pool design.
/// Panic for zero workers or zero morsel size.
pub fn morsels(data: &Columns, mask: u8, size: usize, workers: usize) -> u64 {
    assert!(workers > 0 && size > 0);
    let next = AtomicUsize::new(0);
    std::thread::scope(|scope| {
        let handles: Vec<_> = (0..workers)
            .map(|_| {
                let next = &next;
                scope.spawn(move || {
                    let mut sum = 0_u64;
                    while let Some(range) = claim(next, data.len(), size) {
                        sum = sum.wrapping_add(fused_range(data, range, mask));
                    }
                    sum
                })
            })
            .collect();
        handles
            .into_iter()
            .fold(0_u64, |sum, h| sum.wrapping_add(h.join().unwrap()))
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn scans_agree_across_partial_batches() {
        for n in [0, 1, 7, 31, 1025] {
            let d = Columns::generated(n);
            for mask in [0, 1, 63, 255] {
                let expected = d.oracle(mask);
                assert_eq!(dispatched(&d, mask), expected);
                assert_eq!(fused(&d, mask), expected);
                for b in [1, 3, 16, 1024, usize::MAX] {
                    assert_eq!(batched(&d, mask, b), expected);
                }
            }
        }
    }
    #[test]
    fn nulls_and_no_matches() {
        let d = Columns::new(vec![1, 0, 0], vec![5, 99, 7], vec![1, 0, 1]);
        assert_eq!(fused(&d, 1), 7);
        let d = Columns::new(vec![1; 3], vec![5; 3], vec![1; 3]);
        assert_eq!(batched(&d, 1, 2), 0);
    }
    #[test]
    fn explicit_overflow_contract() {
        let d = Columns::new(vec![0; 2], vec![u64::MAX, 2], vec![1; 2]);
        assert_eq!(d.oracle(0), 1);
        assert_eq!(dispatched(&d, 0), 1);
        assert_eq!(batched(&d, 0, 1), 1);
        assert_eq!(morsels(&d, 0, 1, 2), 1);
    }
    #[test]
    fn parallel_sums_agree() {
        for n in [0, 7, 1025] {
            let d = Columns::generated(n);
            for m in [1, 3, 512, usize::MAX] {
                assert_eq!(morsels(&d, 1, m, 4), d.oracle(1));
            }
        }
    }
    #[test]
    fn concurrent_claims_cover_exactly_once() {
        for n in [0, 1, 127, 1025] {
            for size in [1, 3, 128, usize::MAX] {
                let next = AtomicUsize::new(0);
                let ranges = std::thread::scope(|s| {
                    let hs: Vec<_> = (0..4)
                        .map(|_| {
                            s.spawn(|| {
                                let mut rs = Vec::new();
                                while let Some(r) = claim(&next, n, size) {
                                    rs.push(r);
                                }
                                rs
                            })
                        })
                        .collect();
                    hs.into_iter()
                        .flat_map(|h| h.join().unwrap())
                        .collect::<Vec<_>>()
                });
                let mut visits = vec![0; n];
                for r in ranges {
                    for i in r {
                        visits[i] += 1;
                    }
                }
                assert!(visits.iter().all(|&v| v == 1));
                assert_eq!(next.load(Ordering::Relaxed), n);
            }
        }
    }
    #[test]
    fn exhausted_is_not_completed() {
        let next = AtomicUsize::new(0);
        let unprocessed = claim(&next, 7, 7).unwrap();
        assert!(claim(&next, 7, 7).is_none());
        assert_eq!(unprocessed.len(), 7);
    }
    #[test]
    #[should_panic]
    fn rejects_lengths() {
        Columns::new(vec![0], vec![], vec![1]);
    }
    #[test]
    #[should_panic]
    fn rejects_validity() {
        Columns::new(vec![0], vec![1], vec![2]);
    }
    #[test]
    #[should_panic]
    fn rejects_zero_batch() {
        batched(&Columns::generated(1), 0, 0);
    }
    #[test]
    #[should_panic]
    fn rejects_zero_workers() {
        morsels(&Columns::generated(1), 0, 1, 0);
    }
    #[test]
    #[should_panic]
    fn rejects_zero_morsel() {
        morsels(&Columns::generated(1), 0, 0, 1);
    }
}
