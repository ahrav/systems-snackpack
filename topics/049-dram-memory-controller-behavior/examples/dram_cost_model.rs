//! Prints the lesson's illustrative DRAM accounting values.
//!
//! The example uses hard-coded teaching inputs and does not collect host
//! measurements. The values do not describe a complete memory-access latency.

use dram_memory_controller_behavior::{
    BankState, BankStateMix, DramTiming, expected_device_component_ns, pin_bandwidth,
    refresh_duty_fraction, required_inflight,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let timing = DramTiming::new(14.0, 2.5, 14.0, 14.0)?;
    let mix = BankStateMix::new(0.50, 0.20, 0.30)?;
    let expected = expected_device_component_ns(timing, mix)?;

    let required = required_inflight(20e9, 100e-9, 64.0)?;
    let integer_slots = required.ceil() as u64;
    let pin = pin_bandwidth(4.8e9, 32)?;
    let refresh = refresh_duty_fraction(295.0, 3_900.0)?;

    println!(
        "device components (ns): hit={:.2}, closed={:.2}, conflict={:.2}",
        timing.device_component_ns(BankState::Hit),
        timing.device_component_ns(BankState::Closed),
        timing.device_component_ns(BankState::Conflict),
    );
    println!("expected device component: {expected:.2} ns");
    println!("required average in flight: {required:.2}; integer slots: {integer_slots}");
    println!("raw data-pin bandwidth: {:.2} GB/s", pin / 1e9);
    println!(
        "nominal refresh schedule fraction: {refresh:.6} ({:.4}%)",
        refresh * 100.0
    );

    Ok(())
}
