//! Prints the checked planning substitutions used in the topic README.

use packet_steering_interrupts::{
    interrupt_cost, queue_utilization, rfs_cost_delta, rps_cost, table_alias_probability,
    xps_core_savings,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let queue = queue_utilization(&[50_000.0; 8], 700.0, 3e9)?;
    let elephant = queue_utilization(&[5_000_000.0, 350_000.0], 700.0, 3e9)?;
    let interrupt = interrupt_cost(3.2e6, 32, 0.8e-6)?;
    let rps = rps_cost(3.2e6, 40.0, 80.0, 1.0, 60.0, 900.0, 32, 3e9)?;
    let rfs = rfs_cost_delta(3.2e6, 30.0, 2_000.0, 10_000, 80.0, 3e9)?;
    let alias = table_alias_probability(10_000, 65_536)?;
    let xps = xps_core_savings(3.2e6, 120.0, 40.0, 3e9)?;

    println!("balanced_queue_utilization={:.6}", queue.utilization);
    println!("elephant_queue_utilization={:.6}", elephant.utilization);
    println!(
        "interrupts_per_second={:.0}",
        interrupt.interrupts_per_second
    );
    println!("interrupt_required_cores={:.6}", interrupt.required_cores);
    println!("rps_required_cores={:.6}", rps.required_cores);
    println!("rfs_required_cores_delta={:.6}", rfs.required_cores_delta);
    println!("rfs_table_alias_probability={alias:.6}");
    println!("xps_modeled_core_savings={xps:.6}");
    Ok(())
}
