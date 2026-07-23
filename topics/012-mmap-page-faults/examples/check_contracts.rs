//! Checks the cold-file evidence contract and process schedule.

use systems_snackpack_topic_012::{
    Observation, amortized_ns_per_fault, balanced_schedule, faults_per_page, validate_cold_file,
};

fn main() {
    let observation = Observation {
        pages: 8_192,
        touch_ns: 4_000_000_000,
        minor_faults: 0,
        major_faults: 8_192,
        resident_before: 0,
        resident_after: 8_192,
    };
    validate_cold_file(observation).expect("fixture satisfies the cold-file evidence contract");
    assert_eq!(faults_per_page(observation), Some(1.0));
    assert_eq!(amortized_ns_per_fault(observation), Some(488_281.25));
    assert_eq!(balanced_schedule().len(), 8);
    println!("validated cold-file evidence and eight-block schedule");
    // The shell runner and Python validator hold independent copies of the
    // schedule as a double-entry control; each cross-checks itself against
    // these lines before any measurement process starts.
    for block in balanced_schedule() {
        println!("SCHEDULE {}", block.join(" "));
    }
}
