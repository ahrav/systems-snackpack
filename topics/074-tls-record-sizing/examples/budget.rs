//! Count TLS bytes with independently flushed application writes.
use tls_record_sizing::budget;
fn main() {
    for cap in [1024, 4096, 16384] {
        println!(
            "cap={cap} ready={:?} flushed={:?}",
            budget(&[65536], cap, 16385, 0),
            budget(&[128; 512], cap, 16385, 0)
        );
    }
}
