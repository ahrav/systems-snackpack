//! Prints the lesson's page-cache cost checks.
//!
//! The inputs are teaching values, not host measurements. The calculations
//! compare accounting models; they do not predict Linux policy or device speed.

use page_cache_io::{
    DirtyHeadroom, dirty_headroom, expected_read_seconds, read_amplification,
    required_direct_queue_depth, required_readahead_bytes, reuse_ledger,
};

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let expected = expected_read_seconds(0.95, 4e-6, 1e-3)?;
    let window = required_readahead_bytes(1024.0_f64.powi(3), 80e-6, 42e-6)?;
    let amplification = read_amplification(128.0 * 1024.0, 4.0 * 1024.0)?;
    let headroom = dirty_headroom(4.8e9, 2.4e9, 4e9, 1e9)?;
    let depth = required_direct_queue_depth(3.0 * 1024.0_f64.powi(3), 100e-6, 4096.0)?;
    let gib = 1024.0_f64.powi(3);
    let ledger = reuse_ledger(8.0 * gib, 3.0 * gib, 30.0 * gib, 2, 0.4, 0.02)?;

    println!("expected read service: {:.1} us", expected * 1e6);
    println!("read-ahead window: {:.0} KiB", window / 1024.0);
    println!("read amplification: {amplification:.0}x");
    match headroom {
        DirtyHeadroom::Unbounded => println!("dirty headroom: unbounded in this model"),
        DirtyHeadroom::Seconds(seconds) => println!("dirty headroom: {seconds:.1} s"),
    }
    println!("direct-I/O queue-depth lower bound: {depth}");
    println!(
        "two passes: buffered {:.2} s, direct {:.2} s",
        ledger.buffered_seconds, ledger.direct_seconds
    );

    Ok(())
}
