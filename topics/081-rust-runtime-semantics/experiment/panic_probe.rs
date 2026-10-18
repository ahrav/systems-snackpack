//! Subprocess probe: abort behavior must not kill the test runner.
struct Guard;
impl Drop for Guard {
    fn drop(&mut self) {
        eprintln!("DROP_MARKER");
    }
}
fn main() {
    let result = std::panic::catch_unwind(|| {
        let _guard = Guard;
        panic!("intentional probe");
    });
    assert!(result.is_err());
    println!("CAUGHT_MARKER");
}
