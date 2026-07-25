//! Checks scalar, selected, cached, and chunked dispatch on boundary lengths.

use systems_snackpack_topic_014::{
    count_eq_cached_chunks, count_eq_detect_chunks, count_eq_dispatch_once, count_eq_scalar,
    resolve_best, resolve_cached,
};

fn main() {
    for length in [0, 1, 15, 16, 17, 31, 32, 33, 255, 256, 257, 4_097] {
        let input: Vec<u8> = (0..length)
            .map(|index| {
                let mixed = (index as u64)
                    .wrapping_mul(0x9e37_79b9_7f4a_7c15)
                    .rotate_left(17)
                    ^ 0xd1b5_4a32_d192_ed03;
                (mixed >> 56) as u8
            })
            .collect();
        for needle in [0x00, 0x5a, 0xff] {
            let expected = count_eq_scalar(&input, needle);
            assert_eq!(resolve_best().count(&input, needle), expected);
            assert_eq!(resolve_cached().count(&input, needle), expected);
            assert_eq!(count_eq_dispatch_once(&input, needle), expected);
            for chunk_size in [1, 15, 16, 31, 32, 255, 256, 257] {
                assert_eq!(
                    count_eq_cached_chunks(&input, needle, chunk_size),
                    Ok(expected)
                );
                assert_eq!(
                    count_eq_detect_chunks(&input, needle, chunk_size),
                    Ok(expected)
                );
            }
        }
    }

    assert!(count_eq_cached_chunks(&[1], 1, 0).is_err());
    assert!(count_eq_detect_chunks(&[1], 1, 0).is_err());
    println!(
        "validated scalar, {}, cached, and chunked dispatch contracts",
        resolve_best().kind().as_str()
    );
}
