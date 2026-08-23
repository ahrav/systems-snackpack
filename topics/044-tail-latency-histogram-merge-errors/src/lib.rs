//! Checked contracts for merging latency histograms.
//!
//! A percentile is an order statistic: it identifies a position after all
//! observations are combined and sorted. It is not an additive summary, so
//! averaging shard percentiles does not recover the percentile of their union.
//!
//! [`IntervalHistogram`] assigns every observation to one non-overlapping
//! bucket under an explicit [`BucketSchema`]. [`CumulativeHistogram`] stores
//! those per-bucket counts accumulated over reporting time by one producer; it
//! is not cumulative across bucket boundaries. For cumulative exports, call
//! [`CumulativeHistogram::delta_since`] before merging compatible window
//! deltas. [`IntervalHistogram::merge_compatible`] rejects unequal schemas,
//! and `delta_since` rejects schema changes and counter resets.

use std::fmt;

/// A histogram's ordered inclusive upper bounds, expressed in microseconds.
///
/// Two histograms are directly mergeable only when these bounds have identical
/// values in identical positions. A schema is part of the data, not display
/// metadata.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct BucketSchema {
    upper_bounds_us: Vec<u64>,
}

impl BucketSchema {
    /// Creates a strictly increasing, nonempty bucket schema.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::EmptySchema`] if `upper_bounds_us` is empty.
    /// - [`HistogramError::NonIncreasingBounds`] if adjacent bounds are equal
    ///   or descending.
    pub fn new(upper_bounds_us: Vec<u64>) -> Result<Self, HistogramError> {
        if upper_bounds_us.is_empty() {
            return Err(HistogramError::EmptySchema);
        }
        if upper_bounds_us.windows(2).any(|pair| pair[0] >= pair[1]) {
            return Err(HistogramError::NonIncreasingBounds);
        }
        Ok(Self { upper_bounds_us })
    }

    /// Returns the inclusive upper bounds in microseconds.
    #[must_use]
    pub fn upper_bounds_us(&self) -> &[u64] {
        &self.upper_bounds_us
    }

    fn bucket_index(&self, value_us: u64) -> Result<usize, HistogramError> {
        let index = self
            .upper_bounds_us
            .partition_point(|bound| *bound < value_us);
        if index < self.upper_bounds_us.len() {
            Ok(index)
        } else {
            Err(HistogramError::ObservationOutOfRange {
                value_us,
                maximum_us: *self
                    .upper_bounds_us
                    .last()
                    .expect("a validated schema is nonempty"),
            })
        }
    }
}

/// A nearest-rank answer bounded by one histogram bucket.
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct QuantileBracket {
    /// The previous bucket's upper bound, excluded from this bucket. `None`
    /// identifies the first bucket.
    pub lower_exclusive_us: Option<u64>,
    /// This bucket's inclusive upper bound.
    pub upper_inclusive_us: u64,
    /// One-based nearest rank selected from the union.
    pub rank: u64,
    /// Number of observations in the union.
    pub total_count: u64,
}

/// A histogram that assigns each observation to one non-overlapping bucket.
///
/// Counts are not cumulative across bucket boundaries: each observation
/// contributes to exactly one entry in [`Self::counts`].
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct IntervalHistogram {
    schema: BucketSchema,
    counts: Vec<u64>,
}

impl IntervalHistogram {
    /// Creates an empty histogram under `schema`.
    #[must_use]
    pub fn empty(schema: BucketSchema) -> Self {
        let counts = vec![0; schema.upper_bounds_us.len()];
        Self { schema, counts }
    }

    /// Creates a histogram from checked interval counts.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::BucketCountMismatch`] if the number of counts does
    ///   not equal the number of schema bounds.
    /// - [`HistogramError::ArithmeticOverflow`] if the total count cannot fit
    ///   in `u64`.
    pub fn from_counts(schema: BucketSchema, counts: Vec<u64>) -> Result<Self, HistogramError> {
        if counts.len() != schema.upper_bounds_us.len() {
            return Err(HistogramError::BucketCountMismatch {
                bounds: schema.upper_bounds_us.len(),
                counts: counts.len(),
            });
        }
        counts.iter().try_fold(0_u64, |sum, count| {
            sum.checked_add(*count)
                .ok_or(HistogramError::ArithmeticOverflow)
        })?;
        Ok(Self { schema, counts })
    }

    /// Records one observation in microseconds.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::ObservationOutOfRange`] if `value_us` exceeds the
    ///   schema's final inclusive bound.
    /// - [`HistogramError::ArithmeticOverflow`] if the selected bucket already
    ///   contains `u64::MAX` observations.
    pub fn record(&mut self, value_us: u64) -> Result<(), HistogramError> {
        let index = self.schema.bucket_index(value_us)?;
        self.counts[index] = self.counts[index]
            .checked_add(1)
            .ok_or(HistogramError::ArithmeticOverflow)?;
        Ok(())
    }

    /// Returns the schema that gives every count its meaning.
    #[must_use]
    pub fn schema(&self) -> &BucketSchema {
        &self.schema
    }

    /// Returns non-cumulative interval counts.
    #[must_use]
    pub fn counts(&self) -> &[u64] {
        &self.counts
    }

    /// Returns the checked sum of all bucket counts.
    ///
    /// # Errors
    ///
    /// Returns [`HistogramError::ArithmeticOverflow`] if the sum cannot fit in
    /// `u64`.
    pub fn total_count(&self) -> Result<u64, HistogramError> {
        self.counts.iter().try_fold(0_u64, |sum, count| {
            sum.checked_add(*count)
                .ok_or(HistogramError::ArithmeticOverflow)
        })
    }

    /// Adds another histogram only when both schemas are identical.
    ///
    /// The operation is transactional: any error leaves `self` unchanged.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::SchemaMismatch`] if the bucket schemas differ.
    /// - [`HistogramError::ArithmeticOverflow`] if any corresponding count sum
    ///   cannot fit in `u64`.
    pub fn merge_compatible(&mut self, other: &Self) -> Result<(), HistogramError> {
        if self.schema != other.schema {
            return Err(HistogramError::SchemaMismatch);
        }
        let merged = self
            .counts
            .iter()
            .zip(&other.counts)
            .map(|(left, right)| {
                left.checked_add(*right)
                    .ok_or(HistogramError::ArithmeticOverflow)
            })
            .collect::<Result<Vec<_>, _>>()?;
        self.counts = merged;
        Ok(())
    }

    /// Returns the bucket containing the nearest-rank quantile.
    ///
    /// For `N` observations, the selected one-based rank is
    /// `ceil(N * numerator / denominator)`. The fraction must be in `(0, 1]`.
    /// The result is the observed bucket interval, not an invented point
    /// estimate within that bucket.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::InvalidQuantile`] if the denominator or numerator
    ///   is zero, or if the numerator exceeds the denominator.
    /// - [`HistogramError::EmptyHistogram`] if every bucket count is zero.
    /// - [`HistogramError::ArithmeticOverflow`] if total-count, rank, or
    ///   cumulative-count arithmetic cannot fit in `u64`.
    /// - [`HistogramError::CountInvariantBroken`] if the stored counts do not
    ///   cover the computed rank.
    pub fn nearest_rank_bracket(
        &self,
        numerator: u64,
        denominator: u64,
    ) -> Result<QuantileBracket, HistogramError> {
        if numerator == 0 || denominator == 0 || numerator > denominator {
            return Err(HistogramError::InvalidQuantile);
        }
        let total_count = self.total_count()?;
        if total_count == 0 {
            return Err(HistogramError::EmptyHistogram);
        }
        let product = total_count
            .checked_mul(numerator)
            .ok_or(HistogramError::ArithmeticOverflow)?;
        let rank = product
            .checked_add(denominator - 1)
            .ok_or(HistogramError::ArithmeticOverflow)?
            / denominator;

        let mut cumulative = 0_u64;
        for (index, count) in self.counts.iter().enumerate() {
            cumulative = cumulative
                .checked_add(*count)
                .ok_or(HistogramError::ArithmeticOverflow)?;
            if cumulative >= rank {
                return Ok(QuantileBracket {
                    lower_exclusive_us: index
                        .checked_sub(1)
                        .map(|previous| self.schema.upper_bounds_us[previous]),
                    upper_inclusive_us: self.schema.upper_bounds_us[index],
                    rank,
                    total_count,
                });
            }
        }
        Err(HistogramError::CountInvariantBroken)
    }

    /// Coarsens into an ordered subset of the source bounds with the same final
    /// bound.
    ///
    /// Coarsening combines complete old buckets. It never splits a bucket or
    /// pretends that detail discarded by an earlier producer still exists.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::InvalidCoarsening`] if the schemas have different
    ///   final bounds or any target bound is absent from the source schema.
    /// - [`HistogramError::ArithmeticOverflow`] if a combined target count
    ///   cannot fit in `u64`.
    pub fn coarsen(&self, target: BucketSchema) -> Result<Self, HistogramError> {
        if self.schema.upper_bounds_us.last() != target.upper_bounds_us.last()
            || target
                .upper_bounds_us
                .iter()
                .any(|bound| self.schema.upper_bounds_us.binary_search(bound).is_err())
        {
            return Err(HistogramError::InvalidCoarsening);
        }

        let mut result = Self::empty(target);
        for (source_index, count) in self.counts.iter().enumerate() {
            let source_upper = self.schema.upper_bounds_us[source_index];
            let target_index = result
                .schema
                .upper_bounds_us
                .partition_point(|bound| *bound < source_upper);
            result.counts[target_index] = result.counts[target_index]
                .checked_add(*count)
                .ok_or(HistogramError::ArithmeticOverflow)?;
        }
        Ok(result)
    }
}

/// Per-interval bucket counters accumulated over time by one producer.
///
/// "Cumulative" describes successive reporting snapshots, not overlap between
/// value buckets. Each entry corresponds to one [`BucketSchema`] interval and
/// must never decrease unless the producer resets.
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct CumulativeHistogram {
    schema: BucketSchema,
    interval_totals: Vec<u64>,
}

impl CumulativeHistogram {
    /// Creates a cumulative snapshot from per-bucket counters.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::BucketCountMismatch`] if the number of counters does
    ///   not equal the number of schema bounds.
    /// - [`HistogramError::ArithmeticOverflow`] if the counter sum cannot fit
    ///   in `u64`.
    pub fn new(schema: BucketSchema, interval_totals: Vec<u64>) -> Result<Self, HistogramError> {
        IntervalHistogram::from_counts(schema.clone(), interval_totals.clone())?;
        Ok(Self {
            schema,
            interval_totals,
        })
    }

    /// Subtracts an older snapshot, rejecting reset or schema-change windows.
    ///
    /// # Errors
    ///
    /// - [`HistogramError::SchemaMismatch`] if the snapshots use different
    ///   bucket schemas.
    /// - [`HistogramError::CounterReset`] if any current counter is lower than
    ///   its older value.
    pub fn delta_since(&self, older: &Self) -> Result<IntervalHistogram, HistogramError> {
        if self.schema != older.schema {
            return Err(HistogramError::SchemaMismatch);
        }
        let counts = self
            .interval_totals
            .iter()
            .zip(&older.interval_totals)
            .map(|(current, previous)| {
                current
                    .checked_sub(*previous)
                    .ok_or(HistogramError::CounterReset)
            })
            .collect::<Result<Vec<_>, _>>()?;
        IntervalHistogram::from_counts(self.schema.clone(), counts)
    }
}

/// Errors that prevent a histogram result from preserving its meaning.
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum HistogramError {
    /// A schema has no buckets.
    EmptySchema,
    /// Bucket bounds are duplicated or out of order.
    NonIncreasingBounds,
    /// The number of bounds and counts differs.
    BucketCountMismatch {
        /// Number of bounds in the schema.
        bounds: usize,
        /// Number of supplied interval counts.
        counts: usize,
    },
    /// An observation exceeds the schema's final bound.
    ObservationOutOfRange {
        /// Rejected observation in microseconds.
        value_us: u64,
        /// Final inclusive boundary in microseconds.
        maximum_us: u64,
    },
    /// Two operands use different bucket meanings.
    SchemaMismatch,
    /// A cumulative counter decreased between snapshots.
    CounterReset,
    /// Count or rank arithmetic overflowed.
    ArithmeticOverflow,
    /// A quantile was outside `(0, 1]`.
    InvalidQuantile,
    /// A quantile was requested from no observations.
    EmptyHistogram,
    /// A coarser schema would require splitting or extending a source bucket.
    InvalidCoarsening,
    /// Stored counts could not satisfy the histogram invariant.
    CountInvariantBroken,
}

impl fmt::Display for HistogramError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(formatter, "{self:?}")
    }
}

impl std::error::Error for HistogramError {}

/// Adds four bucket counts with overflow detection for code-generation review.
///
/// The operation computes all sums before storing any of them. A `false`
/// return therefore leaves `destination` unchanged. The stable, non-inlined
/// symbol exists only so the experiment can retain exact-build assembly.
#[unsafe(no_mangle)]
#[inline(never)]
pub fn topic44_checked_merge_four(destination: &mut [u64; 4], source: &[u64; 4]) -> bool {
    let Some(first) = destination[0].checked_add(source[0]) else {
        return false;
    };
    let Some(second) = destination[1].checked_add(source[1]) else {
        return false;
    };
    let Some(third) = destination[2].checked_add(source[2]) else {
        return false;
    };
    let Some(fourth) = destination[3].checked_add(source[3]) else {
        return false;
    };
    *destination = [first, second, third, fourth];
    true
}

#[cfg(test)]
mod tests {
    use super::*;

    fn schema() -> BucketSchema {
        BucketSchema::new(vec![1, 10, 100, 1_000]).expect("valid test schema")
    }

    #[test]
    fn union_quantile_differs_from_both_averages_of_shard_quantiles() {
        let mut first = IntervalHistogram::empty(schema());
        for _ in 0..990 {
            first.record(1).expect("in range");
        }
        for _ in 0..10 {
            first.record(100).expect("in range");
        }
        let mut second = IntervalHistogram::empty(schema());
        for _ in 0..10 {
            second.record(1_000).expect("in range");
        }

        first.merge_compatible(&second).expect("same schema");
        let bracket = first.nearest_rank_bracket(99, 100).expect("nonempty");
        assert_eq!(bracket.rank, 1_000);
        assert_eq!(bracket.lower_exclusive_us, Some(10));
        assert_eq!(bracket.upper_inclusive_us, 100);
        assert_ne!(bracket.upper_inclusive_us as f64, (1.0 + 1_000.0) / 2.0);
        assert_ne!(
            bracket.upper_inclusive_us as f64,
            (1_000.0 * 1.0 + 10.0 * 1_000.0) / 1_010.0
        );
    }

    #[test]
    fn schema_mismatch_is_rejected_without_mutation() {
        let mut left =
            IntervalHistogram::from_counts(schema(), vec![1, 2, 3, 4]).expect("valid counts");
        let original = left.clone();
        let other_schema = BucketSchema::new(vec![1, 100, 1_000]).expect("valid schema");
        let right =
            IntervalHistogram::from_counts(other_schema, vec![1, 2, 3]).expect("valid counts");
        assert_eq!(
            left.merge_compatible(&right),
            Err(HistogramError::SchemaMismatch)
        );
        assert_eq!(left, original);
    }

    #[test]
    fn counter_reset_is_not_treated_as_a_negative_delta() {
        let older =
            CumulativeHistogram::new(schema(), vec![10, 20, 30, 40]).expect("valid snapshot");
        let current =
            CumulativeHistogram::new(schema(), vec![11, 19, 31, 41]).expect("valid snapshot");
        assert_eq!(
            current.delta_since(&older),
            Err(HistogramError::CounterReset)
        );
    }

    #[test]
    fn exact_coarsening_preserves_count_and_bracket() {
        let source =
            IntervalHistogram::from_counts(schema(), vec![990, 0, 10, 10]).expect("valid counts");
        let target = BucketSchema::new(vec![10, 100, 1_000]).expect("valid target");
        let coarsened = source.coarsen(target).expect("exact coarsening");
        assert_eq!(coarsened.counts(), &[990, 10, 10]);
        assert_eq!(coarsened.total_count(), Ok(1_010));
        assert_eq!(
            coarsened
                .nearest_rank_bracket(99, 100)
                .expect("nonempty")
                .upper_inclusive_us,
            100
        );
    }

    #[test]
    fn four_bucket_merge_is_transactional_on_overflow() {
        let mut destination = [1, u64::MAX, 3, 4];
        let original = destination;
        assert!(!topic44_checked_merge_four(&mut destination, &[1, 1, 1, 1]));
        assert_eq!(destination, original);
    }
}
