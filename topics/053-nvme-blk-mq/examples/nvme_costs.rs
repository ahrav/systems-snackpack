//! Prints one checked substitution through the Topic 53 planning models.
//!
//! Every input is a teaching value. The output reports formula results, not
//! measurements of Linux, `blk-mq`, NVMe hardware, or CPU execution.

use nvme_blk_mq::{
    bandwidth_bytes_per_second, concurrency_limited_iops, cpu_batch_cost, effective_queue_depth,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let depth = effective_queue_depth(512, 8, 64, 128)?;
    let iops = concurrency_limited_iops(depth, 500e-6, 200_000.0)?;
    let bytes_per_second = bandwidth_bytes_per_second(iops, 4096)?;
    let cpu = cpu_batch_cost(iops, 32, 500.0, 800.0, 480.0, 2_500_000_000.0)?;

    println!("model=queue effective_depth={depth}");
    println!("model=iops operations_per_second={iops:.0}");
    println!("model=bandwidth bytes_per_second={bytes_per_second:.0}");
    println!(
        "model=cpu batch_size=32 cycles_per_io={:.1} required_cores={:.4}",
        cpu.cycles_per_io, cpu.required_cores
    );
    println!("boundary=all values are planning-model outputs, not host measurements");

    Ok(())
}
