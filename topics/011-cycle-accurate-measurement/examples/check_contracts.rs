//! Checks the conversion, quantization, and dependency-shape contracts.

use systems_snackpack_topic_011::{
    dependent_chain, endpoint_delta_ns, minimum_batch_duration, scale_absolute_ticks,
};

fn main() {
    assert_eq!(endpoint_delta_ns(1, 2, 3, 1, 50), Ok(2));
    assert_eq!(scale_absolute_ticks(2 - 1, 3, 1), Some(1));
    assert_eq!(minimum_batch_duration(40, 10_000), Ok(8_000));

    let checksum = dependent_chain(0x243f_6a88_85a3_08d3, 1_000_000);
    println!(
        "contracts=ok rounding_phase_endpoint_ns=2 direct_delta_ns=1 batch_guard_ns=8000 checksum={checksum:016x}"
    );
}
