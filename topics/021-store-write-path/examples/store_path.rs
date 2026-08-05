//! Correctness smoke check for both write paths and both STLF geometries.

use std::sync::atomic::{AtomicU64, Ordering, fence};
use topic_021_store_write_path::{
    AlignedBuffer, STLF_SEED, StlfMode, WriteMode, architecture_name, publish_pattern, run_stlf,
    stlf_oracle, write_kernels_supported,
};

fn main() {
    assert!(
        write_kernels_supported(),
        "required architecture features are unavailable"
    );

    for mode in [WriteMode::Temporal, WriteMode::NonTemporal] {
        let mut destination = AlignedBuffer::new(64 * 1024);
        destination.fill(0xa5);
        let ready = AtomicU64::new(0);
        publish_pattern(mode, &mut destination, &ready);
        fence(Ordering::SeqCst);
        assert_eq!(ready.load(Ordering::Acquire), 1);
        assert_eq!(destination.verify_pattern().bad_words, 0);
    }

    for mode in [StlfMode::Exact, StlfMode::Partial] {
        let mut buffer = AlignedBuffer::new(64);
        buffer.initialize_stlf_fixture();
        let observed = run_stlf(mode, &mut buffer, 4_096, STLF_SEED);
        assert_eq!(observed, stlf_oracle(mode, 4_096, STLF_SEED));
    }

    println!(
        "{{\"kind\":\"check\",\"architecture\":\"{}\",\"temporal\":true,\"nontemporal\":true,\"stlf_exact\":true,\"stlf_partial\":true}}",
        architecture_name()
    );
}
