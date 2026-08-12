//! Small executable smoke benchmark for the two modeled layouts.

use database_index_internals::{Treatment, run_treatment};

fn main() {
    for treatment in [Treatment::Narrow, Treatment::Covering] {
        let result = run_treatment(treatment, 1 << 18, 1 << 14, 4).unwrap();
        let lookups = result.queries * result.reps;
        println!(
            "treatment={} lookups={} ns_per_lookup={:.3} checksum={}",
            treatment.as_str(),
            lookups,
            result.steady.as_nanos() as f64 / lookups as f64,
            result.checksum
        );
    }
}
