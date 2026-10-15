//! Run one saturated batch: MODE CAPACITY PRODUCERS CONSUMERS ITEMS_PER_PRODUCER.
use bounded_mpmc_queue::{Mode, transfer};
fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        6,
        "usage: bounded-mpmc-queue array|mutex capacity producers consumers per_producer"
    );
    let mode = match args[1].as_str() {
        "array" => Mode::Array,
        "mutex" => Mode::Mutex,
        _ => panic!("mode must be array or mutex"),
    };
    let nums: Vec<usize> = args[2..].iter().map(|a| a.parse().unwrap()).collect();
    let r = transfer(mode, nums[0], nums[1], nums[2], nums[3]);
    println!(
        "{{\"mode\":\"{}\",\"capacity\":{},\"producers\":{},\"consumers\":{},\"per_producer\":{},\"jobs\":{},\"elapsed_ns\":{},\"outer_retries\":{},\"verified\":true}}",
        args[1],
        nums[0],
        nums[1],
        nums[2],
        nums[3],
        r.jobs,
        r.elapsed.as_nanos(),
        r.retries
    );
}
