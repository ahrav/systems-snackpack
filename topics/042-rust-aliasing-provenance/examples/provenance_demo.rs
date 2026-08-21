//! Deterministic aliasing and provenance demonstration.

use rust_aliasing_provenance::{
    exposed_address_compares_equal, raw_alias_example, raw_distinct_example, reference_example,
    strict_provenance_write,
};

fn main() {
    let words = strict_provenance_write();
    let exposed_equal = exposed_address_compares_equal();
    let reference = reference_example();
    let raw_distinct = raw_distinct_example();
    let raw_alias = raw_alias_example();

    println!("strict_provenance words={words:?} dereferenced_within_live_allocation=yes");
    println!(
        "exposed_address comparison={} dereferenced=no",
        if exposed_equal { "equal" } else { "different" }
    );
    println!(
        "reference distinct_inputs=yes returned={} dst={} src={}",
        reference.returned, reference.destination, reference.source
    );
    println!(
        "raw_distinct same_pointer=no returned={} dst={} src={}",
        raw_distinct.returned, raw_distinct.destination, raw_distinct.source
    );
    println!(
        "raw_alias same_pointer=yes returned={} value={}",
        raw_alias.returned, raw_alias.destination
    );
    let passed = words == [10, 20, 99, 40]
        && exposed_equal
        && reference.returned == 14
        && reference.destination == 8
        && reference.source == 7
        && raw_distinct == reference
        && raw_alias.returned == 15
        && raw_alias.destination == 8
        && raw_alias.source == 8;
    println!(
        "contract result={} timing_reported=no",
        if passed { "PASS" } else { "FAIL" }
    );

    if !passed {
        std::process::exit(1);
    }
}
