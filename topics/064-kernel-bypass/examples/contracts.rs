//! Run the finite ownership and multi-frame packet controls.
use topic064_kernel_bypass::{Assembly, Pool, aligned_frame, wakeup_required};

fn main() {
    let mut pool = Pool::new(32);
    let frames: Vec<_> = (0..32).collect();
    let unsent = pool.transmit(&frames, 20).unwrap().len();
    pool.consume_tx(0).unwrap();
    let early_reuse_rejected = pool.fill(0).is_err();
    pool.complete(0).unwrap();
    pool.reclaim(0).unwrap();
    pool.fill(0).unwrap();
    assert_eq!(
        aligned_frame(2048, 8192, 2048),
        aligned_frame(2050, 8192, 2048)
    );
    let mut assembly = Assembly::new(4).unwrap();
    assert_eq!(assembly.push(1, true).unwrap(), None);
    assert_eq!(assembly.push(2, true).unwrap(), None);
    let pending_at_batch_end = assembly.pending();
    let completed = assembly.push(3, false).unwrap().unwrap();
    println!(
        "early_reuse_rejected={early_reuse_rejected} unsent={unsent} aligned_alias=same_frame"
    );
    println!("pending_at_batch_end={pending_at_batch_end} completed_frames={completed:?}");
    println!("wakeup_required={}", wakeup_required(true, true));
}
