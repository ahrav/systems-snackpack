//! Stream interface: arguments are policy, measurement delay, actuation delay.
//! Stdin lines contain arrivals and a 0/1 measurement-valid flag.
use feedback_control::{Policy, simulate};
use std::io::{self, Read};

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(
        args.len(),
        4,
        "usage: feedback-control fast|slow|feedforward measurement_delay actuation_delay"
    );
    let policy = match args[1].as_str() {
        "fast" => Policy::Fast,
        "slow" => Policy::Slow,
        "feedforward" => Policy::FeedForward,
        _ => panic!("unknown policy"),
    };
    let mut input = String::new();
    io::stdin().read_to_string(&mut input).unwrap();
    let pairs: Vec<_> = input
        .lines()
        .map(|line| {
            let fields: Vec<_> = line.split_whitespace().collect();
            assert_eq!(fields.len(), 2);
            assert!(fields[1] == "0" || fields[1] == "1");
            (fields[0].parse::<i64>().unwrap(), fields[1] == "1")
        })
        .collect();
    let (arrivals, valid): (Vec<_>, Vec<_>) = pairs.into_iter().unzip();
    for row in simulate(
        &arrivals,
        &valid,
        policy,
        args[2].parse().unwrap(),
        args[3].parse().unwrap(),
    ) {
        println!(
            "{} {} {} {}",
            row.ready, row.desired, row.command, row.queue
        );
    }
}
