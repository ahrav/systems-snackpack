//! Checks all three kernels on an odd, padded layout, two modulo-index cycles,
//! and the recorded process schedule.
//!
//! On success, the executable emits the library schedule as `SCHEDULE` records
//! so external runner and analysis copies can detect schedule drift before
//! measurement.

use systems_snackpack_topic_013::{
    balanced_schedule, modulo_sets_visited, schedule_is_order_balanced, transpose_naive,
    transpose_recursive, transpose_tiled,
};

fn main() {
    let n = 257;
    let leading_dimension = 263;
    let mut source = vec![u64::MAX; n * leading_dimension];
    for row in 0..n {
        for column in 0..n {
            source[row * leading_dimension + column] =
                (row as u64) * 131 + (column as u64) * 17 + 7;
        }
    }

    let mut destination = vec![u64::MAX; n * leading_dimension];
    for kernel in ["naive", "tiled", "recursive"] {
        destination.fill(u64::MAX);
        match kernel {
            "naive" => transpose_naive(&source, &mut destination, n, leading_dimension),
            "tiled" => transpose_tiled(&source, &mut destination, n, leading_dimension, 31),
            "recursive" => transpose_recursive(&source, &mut destination, n, leading_dimension),
            _ => unreachable!(),
        }
        .expect("the fixture has a valid padded layout");
        for row in 0..n {
            for column in 0..n {
                assert_eq!(
                    destination[column * leading_dimension + row],
                    source[row * leading_dimension + column]
                );
            }
            for column in n..leading_dimension {
                assert_eq!(destination[row * leading_dimension + column], u64::MAX);
            }
        }
    }

    assert_eq!(modulo_sets_visited(64, 64), Some(1));
    assert_eq!(modulo_sets_visited(64, 65), Some(64));
    assert!(schedule_is_order_balanced(&balanced_schedule()));
    println!("validated three kernels, padding, modulo cycles, and schedule");
    // Emit the canonical library schedule for external cross-copy drift checks.
    for block in balanced_schedule() {
        println!("SCHEDULE {}", block.join(" "));
    }
}
