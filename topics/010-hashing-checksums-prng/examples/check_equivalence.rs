//! Checks CRC parameter vectors, alignment and tails, and fragmented updates.
//!
//! `check_ns` covers the alignment, tail, and fragmentation checks. It excludes
//! the fixed check vectors and deterministic input generation. Treat it as a
//! correctness diagnostic, not a throughput result.
//!
//! Run with `cargo run -p systems-snackpack-topic-010 --example check_equivalence`.

use std::time::Instant;

use systems_snackpack_topic_010::{
    Crc32cKernel, crc32_iso_hdlc_bitwise, crc32c_bitwise, crc32c_table,
};

const MAX_LEN: usize = 8192;
const MAX_OFFSET: usize = 31;
const BOUNDARY_LENGTHS: [usize; 12] = [
    513, 1023, 1024, 1025, 2047, 2048, 2049, 4095, 4096, 4097, 8191, 8192,
];

fn splitmix64(state: &mut u64) -> u64 {
    *state = state.wrapping_add(0x9e37_79b9_7f4a_7c15);
    let mut value = *state;
    value = (value ^ (value >> 30)).wrapping_mul(0xbf58_476d_1ce4_e5b9);
    value = (value ^ (value >> 27)).wrapping_mul(0x94d0_49bb_1331_11eb);
    value ^ (value >> 31)
}

fn dataset(len: usize) -> Vec<u8> {
    let mut state = 0x243f_6a88_85a3_08d3_u64;
    (0..len).map(|_| splitmix64(&mut state) as u8).collect()
}

fn check_slice(input: &[u8], label: &str, hardware: Option<Crc32cKernel>) {
    let expected = crc32c_bitwise(input);
    assert_eq!(crc32c_table(input), expected, "table mismatch at {label}");
    if let Some(kernel) = hardware {
        assert_eq!(
            kernel.checksum(input),
            expected,
            "hardware mismatch at {label}"
        );
    }
}

fn main() {
    assert_eq!(crc32c_bitwise(b"123456789"), 0xe306_9283);
    assert_eq!(crc32_iso_hdlc_bitwise(b"123456789"), 0xcbf4_3926);
    assert_ne!(
        crc32c_bitwise(b"123456789"),
        crc32_iso_hdlc_bitwise(b"123456789")
    );

    let bytes = dataset(MAX_OFFSET + MAX_LEN);
    let hardware = Crc32cKernel::detect_hardware();
    let started = Instant::now();
    let mut slice_cases = 0_usize;
    for offset in 0..=MAX_OFFSET {
        for len in 0..=512 {
            check_slice(
                &bytes[offset..offset + len],
                &format_args!("offset={offset} len={len}").to_string(),
                hardware,
            );
            slice_cases += 1;
        }
        for len in BOUNDARY_LENGTHS {
            check_slice(
                &bytes[offset..offset + len],
                &format_args!("offset={offset} len={len}").to_string(),
                hardware,
            );
            slice_cases += 1;
        }
    }

    let table = Crc32cKernel::table();
    let mut split_cases = 0_usize;
    for len in 0..=257 {
        let input = &bytes[..len];
        let expected = crc32c_bitwise(input);
        for split in 0..=len {
            let first = table.update(0, &input[..split]);
            assert_eq!(
                table.update(first, &input[split..]),
                expected,
                "table fragmentation mismatch at len={len} split={split}"
            );
            if let Some(kernel) = hardware {
                let first = kernel.update(0, &input[..split]);
                assert_eq!(
                    kernel.update(first, &input[split..]),
                    expected,
                    "hardware fragmentation mismatch at len={len} split={split}"
                );
            }
            split_cases += 1;
        }
    }

    println!(
        "CHECK crc32c_vector=e3069283 crc32_iso_hdlc_vector=cbf43926 hardware={} slice_cases={} split_cases={} check_ns={}",
        hardware.map_or("unavailable", Crc32cKernel::name),
        slice_cases,
        split_cases,
        started.elapsed().as_nanos()
    );
}
