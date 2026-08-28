//! Prints one hand-checkable prefetch cost model.

use hardware_software_prefetching::{
    ThroughputInputs, in_flight_bytes, required_lead_iterations, throughput_ceiling,
    useful_fraction_break_even,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let distance = required_lead_iterations(240, 6)?;
    let footprint = in_flight_bytes(distance, 1, 64)?;
    let throughput = throughput_ceiling(ThroughputInputs {
        cpu_iterations_per_cycle: 0.5,
        maximum_concurrent_misses: 12.0,
        miss_latency_cycles: 240.0,
        misses_per_iteration: 1.0,
        memory_bytes_per_cycle: 16.0,
        bytes_per_iteration: 64.0,
    })?;
    let break_even = useful_fraction_break_even(0.5, 20.0)?;

    println!("lead distance: {distance} iterations");
    println!("in-flight line footprint: {footprint} bytes");
    println!(
        "modeled ceiling: {:.3} iterations/cycle ({:?})",
        throughput.iterations_per_cycle, throughput.limiting_factor
    );
    println!("minimum useful-prefetch fraction: {break_even:.3}");
    Ok(())
}
