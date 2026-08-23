//! Deterministic oracle for valid and invalid percentile aggregation.
//!
//! The output compares the exact union p99 with two averages of local p99s,
//! then exercises an equal-schema histogram merge, a schema-mismatch rejection,
//! and a cumulative-counter-reset rejection. The experiment compares every
//! fresh process against this output byte for byte.

use histogram_merge_errors::{
    BucketSchema, CumulativeHistogram, HistogramError, IntervalHistogram,
    topic44_checked_merge_four,
};
use std::hint::black_box;

fn nearest_rank(mut values: Vec<u64>, numerator: usize, denominator: usize) -> u64 {
    values.sort_unstable();
    let rank = (values.len() * numerator).div_ceil(denominator);
    values[rank - 1]
}

fn main() -> Result<(), HistogramError> {
    // Keep the stable inspection symbol in the linked example without making
    // its exact lowering part of the program's semantic output.
    let mut codegen_destination = black_box([1_u64, 2, 3, 4]);
    let codegen_source = black_box([10_u64, 20, 30, 40]);
    assert!(topic44_checked_merge_four(
        &mut codegen_destination,
        &codegen_source
    ));
    assert_eq!(codegen_destination, [11, 22, 33, 44]);

    let schema = BucketSchema::new(vec![1, 10, 100, 1_000])?;
    let shard_a = [vec![1; 990], vec![100; 10]].concat();
    let shard_b = vec![1_000; 10];
    let shard_a_p99 = nearest_rank(shard_a.clone(), 99, 100);
    let shard_b_p99 = nearest_rank(shard_b.clone(), 99, 100);
    let mut union = shard_a.clone();
    union.extend_from_slice(&shard_b);
    let exact_union_p99 = nearest_rank(union, 99, 100);

    let unweighted_mean = (shard_a_p99 as f64 + shard_b_p99 as f64) / 2.0;
    let weighted_mean = (shard_a.len() as f64 * shard_a_p99 as f64
        + shard_b.len() as f64 * shard_b_p99 as f64)
        / (shard_a.len() + shard_b.len()) as f64;

    let mut merged = IntervalHistogram::empty(schema.clone());
    for value in shard_a {
        merged.record(value)?;
    }
    let mut second = IntervalHistogram::empty(schema.clone());
    for value in shard_b {
        second.record(value)?;
    }
    merged.merge_compatible(&second)?;
    let bracket = merged.nearest_rank_bracket(99, 100)?;

    let mismatched = IntervalHistogram::empty(BucketSchema::new(vec![1, 100, 1_000])?);
    let mismatch_status = match merged.merge_compatible(&mismatched) {
        Err(HistogramError::SchemaMismatch) => "REJECTED",
        _ => "UNEXPECTED",
    };

    let older = CumulativeHistogram::new(schema.clone(), vec![10, 20, 30, 40])?;
    let reset = CumulativeHistogram::new(schema, vec![11, 19, 31, 41])?;
    let reset_status = match reset.delta_since(&older) {
        Err(HistogramError::CounterReset) => "REJECTED",
        _ => "UNEXPECTED",
    };

    println!("definition=nearest-rank p99 rank=ceil(0.99*N)");
    println!("shard_a count=1000 p99_us={shard_a_p99}");
    println!("shard_b count=10 p99_us={shard_b_p99}");
    println!("union count=1010 exact_p99_us={exact_union_p99}");
    println!("wrong_unweighted_mean_of_local_p99_us={unweighted_mean:.6}");
    println!("wrong_count_weighted_mean_of_local_p99_us={weighted_mean:.6}");
    println!("valid_equal_schema_merge_count={}", merged.total_count()?);
    println!(
        "merged_histogram_p99_bracket_us=({}, {}]",
        bracket
            .lower_exclusive_us
            .expect("p99 is not in first bucket"),
        bracket.upper_inclusive_us
    );
    println!("mismatched_schema_merge={mismatch_status}");
    println!("cumulative_counter_reset={reset_status}");
    println!("status=PASS");
    Ok(())
}
