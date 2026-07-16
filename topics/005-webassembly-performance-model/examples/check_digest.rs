//! Checks the 10-million-step digest shared by the Rust, Wasm, and C paths.

use systems_snackpack_topic_005::{EXPERIMENT_SEED, iterate};

fn main() {
    let digest = iterate(EXPERIMENT_SEED, 10_000_000);
    assert_eq!(digest, 0x8546_3ddc_01d7_d46f);
    println!("digest={digest:#018x}");
}
