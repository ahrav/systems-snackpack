//! Measures one forced branch or register-select kernel per fresh process.
//!
//! One invocation yields one process-level observation for one variant and
//! pattern. The external runner owns pairing, order balancing, and replication.
//! Every process regenerates the same fixed-seed input for its chosen pattern.
//!
//! `timed_ns` spans a `black_box`-wrapped, non-inlined kernel call and the clock
//! read that ends the interval. Argument parsing, condition generation,
//! correctness checks, warmup, process startup, and output remain outside it.

use std::{env, hint::black_box, process, time::Instant};

use systems_snackpack_topic_007::{
    expected_sum, forced_branch_sum, forced_code_shape_supported, forced_select_sum,
};

#[derive(Clone, Copy)]
enum Variant {
    Branch,
    Select,
}

impl Variant {
    fn parse(value: &str) -> Self {
        match value {
            "branch" => Self::Branch,
            "select" => Self::Select,
            other => panic!("unknown variant {other}; use branch or select"),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::Branch => "branch",
            Self::Select => "select",
        }
    }

    fn run(self, conditions: &[u8], repetitions: u64) -> u64 {
        match self {
            Self::Branch => forced_branch_sum(conditions, repetitions),
            Self::Select => forced_select_sum(conditions, repetitions),
        }
    }
}

#[derive(Clone, Copy)]
enum Pattern {
    Zeros,
    Alternating,
    Random,
}

impl Pattern {
    fn parse(value: &str) -> Self {
        match value {
            "zeros" => Self::Zeros,
            "alternating" => Self::Alternating,
            "random" => Self::Random,
            other => panic!("unknown pattern {other}; use zeros, alternating, or random"),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::Zeros => "zeros",
            Self::Alternating => "alternating",
            Self::Random => "random",
        }
    }
}

fn next_u64(state: &mut u64) -> u64 {
    let mut value = *state;
    value ^= value >> 12;
    value ^= value << 25;
    value ^= value >> 27;
    *state = value;
    value.wrapping_mul(2_685_821_657_736_338_717)
}

fn make_conditions(pattern: Pattern, length: usize) -> (Vec<u8>, usize) {
    // Restarting the seed removes per-process input variation within a pattern.
    let mut state = 0xd1b5_4a32_d192_ed03_u64;
    let mut ones = 0_usize;
    let conditions = (0..length)
        .map(|index| {
            let value = match pattern {
                Pattern::Zeros => 0,
                Pattern::Alternating => (index & 1) as u8,
                Pattern::Random => (next_u64(&mut state) >> 63) as u8,
            };
            ones += usize::from(value != 0);
            value
        })
        .collect();
    (conditions, ones)
}

fn argument<'a>(arguments: &'a [String], name: &str) -> Option<&'a str> {
    arguments
        .windows(2)
        .find(|pair| pair[0] == name)
        .map(|pair| pair[1].as_str())
}

fn parse_u64(arguments: &[String], name: &str, default: u64) -> u64 {
    argument(arguments, name)
        .map(|value| {
            value
                .parse()
                .unwrap_or_else(|_| panic!("invalid {name}: {value}"))
        })
        .unwrap_or(default)
}

fn verify() {
    for pattern in [Pattern::Zeros, Pattern::Alternating, Pattern::Random] {
        let (conditions, _) = make_conditions(pattern, 65_536);
        for repetitions in [0, 1, 17] {
            let expected = expected_sum(&conditions, repetitions);
            assert_eq!(forced_branch_sum(&conditions, repetitions), expected);
            assert_eq!(forced_select_sum(&conditions, repetitions), expected);
        }
    }
    println!(
        "VERIFY status=ok fixed_code_shape_supported={}",
        forced_code_shape_supported()
    );
}

fn main() {
    let main_start = Instant::now();
    let arguments = env::args().collect::<Vec<_>>();
    if arguments.iter().any(|argument| argument == "--verify") {
        verify();
        return;
    }
    if !forced_code_shape_supported() {
        eprintln!("controlled timing supports only x86-64 and AArch64");
        process::exit(2);
    }

    let variant = Variant::parse(argument(&arguments, "--variant").expect("missing --variant"));
    let pattern = Pattern::parse(argument(&arguments, "--pattern").expect("missing --pattern"));
    let length = parse_u64(&arguments, "--length", 262_144) as usize;
    let repetitions = parse_u64(&arguments, "--repetitions", 384);
    let warmup_repetitions = parse_u64(&arguments, "--warmup-repetitions", 16);
    let pair = parse_u64(&arguments, "--pair", 0);
    let order = parse_u64(&arguments, "--order", 0);
    assert!(length > 0, "--length must be nonzero");
    assert!(repetitions > 0, "--repetitions must be nonzero");

    let setup_start = Instant::now();
    let (conditions, ones) = make_conditions(pattern, length);
    let setup_ns = setup_start.elapsed().as_nanos();

    let per_scan_expected = expected_sum(&conditions, 1);
    assert_eq!(forced_branch_sum(&conditions, 1), per_scan_expected);
    assert_eq!(forced_select_sum(&conditions, 1), per_scan_expected);

    let warmup_start = Instant::now();
    let warmup_checksum = black_box(variant.run(&conditions, warmup_repetitions));
    let warmup_ns = warmup_start.elapsed().as_nanos();

    let timed_start = Instant::now();
    let checksum = black_box(variant.run(&conditions, repetitions));
    let timed_ns = timed_start.elapsed().as_nanos();
    let expected = expected_sum(&conditions, repetitions);
    assert_eq!(checksum, expected);

    let decisions = length as u128 * repetitions as u128;
    let ns_per_decision = timed_ns as f64 / decisions as f64;
    println!(
        "RESULT pid={} variant={} pattern={} length={} repetitions={} warmup_repetitions={} pair={} order={} ones={} setup_ns={} warmup_ns={} timed_ns={} main_ns={} ns_per_decision={:.9} warmup_checksum={} checksum={}",
        process::id(),
        variant.name(),
        pattern.name(),
        length,
        repetitions,
        warmup_repetitions,
        pair,
        order,
        ones,
        setup_ns,
        warmup_ns,
        timed_ns,
        main_start.elapsed().as_nanos(),
        ns_per_decision,
        warmup_checksum,
        checksum,
    );
}
