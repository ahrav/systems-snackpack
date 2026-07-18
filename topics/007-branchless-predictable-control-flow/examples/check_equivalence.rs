//! Checks the forced branch and select kernels against one shared checksum.

use systems_snackpack_topic_007::{expected_sum, forced_branch_sum, forced_select_sum};

fn next_u64(state: &mut u64) -> u64 {
    let mut value = *state;
    value ^= value >> 12;
    value ^= value << 25;
    value ^= value >> 27;
    *state = value;
    value.wrapping_mul(2_685_821_657_736_338_717)
}

fn main() {
    // The fixed seed makes the correctness corpus identical on every target.
    let mut state = 0xd1b5_4a32_d192_ed03_u64;
    let conditions = (0..65_536)
        .map(|_| (next_u64(&mut state) >> 63) as u8)
        .collect::<Vec<_>>();

    for repetitions in [0, 1, 17] {
        let expected = expected_sum(&conditions, repetitions);
        assert_eq!(forced_branch_sum(&conditions, repetitions), expected);
        assert_eq!(forced_select_sum(&conditions, repetitions), expected);
    }

    println!(
        "status=ok conditions={} repetitions=0,1,17",
        conditions.len()
    );
}
